import clsx from "clsx";
import { motion } from "framer-motion";
import { useSim } from "@/state/SimulationContext";
import { ARCH_NODES } from "@/sim/content";
import { fmtCompact, fmtMs, fmtPct } from "@/lib/format";

/** Live one-line metric shown under each node, derived from sim state. */
function nodeMetric(id: string, s: ReturnType<typeof useSim>["state"]): string {
  switch (id) {
    case "client":
      return `${fmtCompact(s.offeredRps)} req/s offered`;
    case "gateway":
      return `${fmtCompact(s.achievedRps)} req/s · ${fmtPct(s.errorRate)} err`;
    case "redis":
      return `stream ${fmtCompact(s.queueDepth)}`;
    case "scheduler":
      return `batch ${s.avgBatchSize.toFixed(0)} · ${s.lastFlushReason === "MAX_BATCH_SIZE" ? "size" : s.lastFlushReason === "MAX_WAIT_MS" ? "timer" : "idle"}`;
    case "batchq":
      return `${fmtCompact(s.batchQueueDepth)} batches`;
    case "workers":
      return `${s.workers.filter((w) => w.alive).length} up · ${fmtPct(s.meanUtil)} util`;
    case "runtime":
      return `${fmtMs(s.latency.inferenceMs)} infer`;
    case "response":
      return `p99 ${fmtMs(s.p99)}`;
    default:
      return "";
  }
}

function nodeHealth(id: string, s: ReturnType<typeof useSim>["state"]): "ok" | "warn" | "danger" {
  if (id === "workers" && s.workers.some((w) => !w.alive)) return "danger";
  if ((id === "redis" || id === "scheduler" || id === "batchq") && s.queueDepth > 4000) return "danger";
  if ((id === "redis" || id === "scheduler" || id === "batchq") && s.queueDepth > 800) return "warn";
  if (id === "gateway" && s.errorRate > 0.2) return "danger";
  if (id === "gateway" && s.errorRate > 0.02) return "warn";
  if (id === "workers" && s.meanUtil > 0.9) return "warn";
  return "ok";
}

export function FlowDiagram({
  selectedId,
  onSelect,
}: {
  selectedId?: string;
  onSelect?: (id: string) => void;
}) {
  const { state } = useSim();
  // Flow animation params from live state.
  const congested = state.queueDepth > 1500;
  const tokenDuration = state.running ? (congested ? 5.2 : 2.6) / Math.max(0.4, state.controls.speed) : 0;
  const tokenCount = state.running ? Math.min(14, Math.max(3, Math.round(state.achievedRps / 80) + 3)) : 0;
  const errFrac = state.errorRate;

  return (
    <div className="relative">
      {/* animated request tokens travelling across the pipeline */}
      <div className="pointer-events-none absolute left-0 right-0 top-[34px] z-10 h-2">
        {Array.from({ length: tokenCount }).map((_, i) => {
          const isErr = i / Math.max(1, tokenCount) < errFrac;
          return (
            <motion.div
              key={i}
              className={clsx(
                "absolute h-2 w-2 rounded-full",
                isErr ? "bg-danger" : "bg-torch",
              )}
              style={{ boxShadow: isErr ? "0 0 8px #f85149" : "0 0 8px #ee4c2c" }}
              initial={{ left: "2%", opacity: 0 }}
              animate={{ left: isErr ? ["2%", "26%"] : ["2%", "98%"], opacity: [0, 1, 1, isErr ? 0 : 1, 0] }}
              transition={{
                duration: tokenDuration,
                repeat: Infinity,
                delay: (i * tokenDuration) / tokenCount,
                ease: "linear",
              }}
            />
          );
        })}
      </div>

      <div className="flex items-stretch gap-1.5 overflow-x-auto pb-1">
        {ARCH_NODES.map((n, idx) => {
          const health = nodeHealth(n.id, state);
          const selected = selectedId === n.id;
          const ring =
            health === "danger"
              ? "ring-danger/50"
              : health === "warn"
                ? "ring-warn/40"
                : "ring-line";
          return (
            <div key={n.id} className="flex items-center">
              <button
                onClick={() => onSelect?.(n.id)}
                className={clsx(
                  "relative w-[118px] shrink-0 rounded-lg border bg-ink-800 px-2.5 py-2 text-left transition-all",
                  selected ? "border-torch/60 shadow-glow" : "border-line hover:border-line-strong",
                  "ring-1",
                  ring,
                )}
              >
                <div className="flex items-center gap-1.5">
                  <span
                    className={clsx(
                      "h-1.5 w-1.5 rounded-full",
                      health === "ok" ? "bg-ok" : health === "warn" ? "bg-warn" : "bg-danger animate-pulse-line",
                    )}
                  />
                  <span className="truncate text-xs font-semibold text-fg">{n.label}</span>
                </div>
                <div className="mt-0.5 truncate text-[10px] text-fg-faint">{n.sub}</div>
                <div className="mt-1.5 truncate font-mono text-[10px] tabular-nums text-fg-muted">
                  {nodeMetric(n.id, state)}
                </div>
              </button>
              {idx < ARCH_NODES.length - 1 && (
                <div className="mx-0.5 h-px w-3 shrink-0 bg-gradient-to-r from-line-strong to-line" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
