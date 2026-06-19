import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { motion } from "framer-motion";
import { Bar, Panel, PanelHead, PageHeader, Stat, Badge } from "@/components/primitives";
import { TimeSeries } from "@/components/viz/TimeSeries";
import { useSim } from "@/state/SimulationContext";
import { capacityFor, inferenceMs, RUNTIMES } from "@/sim/constants";
import { fmtMs, fmtCompact } from "@/lib/format";

/** Local, faithful animation of one batch fill→flush cycle (same flush rule). */
function BatchTray() {
  const { state } = useSim();
  const { rps, maxBatchSize, maxWaitMs, speed, runtime, modelVersion, batchingEnabled } = state.controls;
  const cap = capacityFor(modelVersion);
  const runtimeMul = RUNTIMES.find((r) => r.id === runtime)?.latencyMul ?? 1;

  const [filled, setFilled] = useState(0);
  const [reason, setReason] = useState<"MAX_BATCH_SIZE" | "MAX_WAIT_MS" | null>(null);
  const [flush, setFlush] = useState(false);
  const startRef = useRef(performance.now());

  const windowSec = maxWaitMs / 1000;
  const fillCount = batchingEnabled ? rps * windowSec : 1;
  const target = batchingEnabled ? Math.min(maxBatchSize, Math.max(1, Math.round(fillCount))) : 1;
  const willFlushBySize = batchingEnabled && (fillCount >= maxBatchSize || state.queueDepth > maxBatchSize);
  const effTarget = willFlushBySize ? maxBatchSize : target;
  const finalReason: "MAX_BATCH_SIZE" | "MAX_WAIT_MS" = willFlushBySize ? "MAX_BATCH_SIZE" : "MAX_WAIT_MS";
  // visual window duration: time to fill (size) or the max-wait timer (time)
  const fillTimeMs = rps > 0 ? (effTarget / rps) * 1000 : maxWaitMs;
  const windowMs = (willFlushBySize ? Math.min(maxWaitMs, fillTimeMs) : maxWaitMs);
  const visMs = Math.max(450, (windowMs / Math.max(0.25, speed)) * 28); // stretch for visibility
  const inferMs = inferenceMs(effTarget, cap) * runtimeMul;

  useEffect(() => {
    startRef.current = performance.now();
    let raf = 0;
    const loop = () => {
      const elapsed = performance.now() - startRef.current;
      const frac = Math.min(1, elapsed / visMs);
      setFilled(Math.round(frac * effTarget));
      if (frac >= 1) {
        setReason(finalReason);
        setFlush(true);
        setTimeout(() => {
          setFlush(false);
          setFilled(0);
          startRef.current = performance.now();
        }, 320);
      } else {
        raf = requestAnimationFrame(loop);
      }
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visMs, effTarget, finalReason]);

  const slots = Math.min(64, Math.max(maxBatchSize, 1));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-4">
        <Stat label="Filling batch" value={`${filled}/${maxBatchSize}`} tone="torch" />
        <Stat label="Window" value={`${maxWaitMs} ms`} />
        <Stat label="Forward pass" value={fmtMs(inferMs)} tone="warn" />
        <div className="ml-auto">
          {flush && reason && (
            <Badge tone={reason === "MAX_BATCH_SIZE" ? "torch" : "info"}>
              flushed: {reason === "MAX_BATCH_SIZE" ? "MAX_BATCH_SIZE reached" : "MAX_WAIT_MS elapsed"}
            </Badge>
          )}
        </div>
      </div>

      {/* the batch tray */}
      <div
        className={clsx(
          "grid gap-1.5 rounded-lg border bg-ink-900 p-3 transition-colors",
          flush ? "border-torch/60" : "border-line",
        )}
        style={{ gridTemplateColumns: `repeat(${Math.min(16, slots)}, minmax(0, 1fr))` }}
      >
        {Array.from({ length: slots }).map((_, i) => {
          const active = i < filled;
          const over = i >= maxBatchSize;
          return (
            <motion.div
              key={i}
              className={clsx(
                "h-6 rounded-sm border",
                over
                  ? "border-line/40 bg-ink-800/40"
                  : active
                    ? flush
                      ? "border-torch bg-torch"
                      : "border-torch/50 bg-torch/40"
                    : "border-line bg-ink-800",
              )}
              animate={active ? { scale: [0.8, 1] } : { scale: 1 }}
              transition={{ duration: 0.15 }}
            />
          );
        })}
      </div>
      <div className="mt-2 flex items-center justify-between text-2xs text-fg-faint">
        <span>requests arriving at {fmtCompact(rps)} req/s</span>
        <span className="mono">
          one forward pass over {effTarget} samples = {fmtMs(inferMs)} →{" "}
          {fmtCompact((effTarget * 1000) / inferMs)} req/s / worker
        </span>
      </div>
    </div>
  );
}

export default function DynamicBatching() {
  const { state, setControls } = useSim();
  const c = state.controls;
  const cap = capacityFor(c.modelVersion);
  const runtimeMul = RUNTIMES.find((r) => r.id === c.runtime)?.latencyMul ?? 1;
  const h = state.history;

  // grounded throughput-vs-batch curve (per worker)
  const curve = [1, 2, 4, 8, 12, 16, 24, 32, 48, 64].map((b) => {
    const ms = inferenceMs(b, cap) * runtimeMul;
    return { t: b, batch: b, throughput: Math.round((b * 1000) / ms), latency: Number(ms.toFixed(2)) };
  });

  return (
    <div>
      <PageHeader
        title="Dynamic Batching"
        desc="The flagship trade-off. The scheduler accumulates requests and flushes a batch when it hits MAX_BATCH_SIZE or MAX_WAIT_MS — whichever comes first. One forward pass over N samples amortizes the fixed per-call overhead."
        source="scheduler/domain/batcher.py · stub_backend.py"
        right={
          <Badge tone={c.batchingEnabled ? "torch" : "danger"}>
            batching {c.batchingEnabled ? "ON" : "OFF"}
          </Badge>
        }
      />

      <div className="space-y-4 p-6">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* controls */}
          <Panel className="lg:col-span-1">
            <PanelHead title="Batcher knobs" sub="changes apply immediately" />
            <div className="space-y-5 p-4">
              <div>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="font-medium text-fg-muted">MAX_BATCH_SIZE</span>
                  <span className="mono text-torch-soft">{c.maxBatchSize}</span>
                </div>
                <input type="range" min={1} max={64} step={1} value={c.maxBatchSize} onChange={(e) => setControls({ maxBatchSize: Number(e.target.value) })} className="w-full accent-torch" />
                <p className="mt-1 text-2xs text-fg-faint">Larger → more throughput, higher tail latency.</p>
              </div>
              <div>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="font-medium text-fg-muted">MAX_WAIT_MS</span>
                  <span className="mono text-info">{c.maxWaitMs} ms</span>
                </div>
                <input type="range" min={1} max={50} step={1} value={c.maxWaitMs} onChange={(e) => setControls({ maxWaitMs: Number(e.target.value) })} className="w-full accent-info" />
                <p className="mt-1 text-2xs text-fg-faint">Bounds how long a request waits to be batched.</p>
              </div>
              <button onClick={() => setControls({ batchingEnabled: !c.batchingEnabled })} className={clsx("btn w-full", c.batchingEnabled ? "btn-accent" : "")}>
                {c.batchingEnabled ? "Disable batching (batch = 1)" : "Enable dynamic batching"}
              </button>

              <div className="grid grid-cols-3 gap-2 border-t border-line pt-4">
                <Stat label="Throughput" value={fmtCompact(state.achievedRps)} tone="torch" />
                <Stat label="p99" value={fmtMs(state.p99)} tone="warn" />
                <Stat label="Device util" value={`${Math.round(state.gpuUtil * 100)}%`} tone="ok" />
              </div>
            </div>
          </Panel>

          {/* batch tray */}
          <Panel className="lg:col-span-2">
            <PanelHead
              title="Batch formation"
              sub="requests fill the tray; flush on size or timer"
              right={
                <span className="mono text-2xs text-fg-faint">
                  flush reason: {state.lastFlushReason === "MAX_BATCH_SIZE" ? "size" : state.lastFlushReason === "MAX_WAIT_MS" ? "timer" : "idle"}
                </span>
              }
            />
            <div className="p-4">
              <BatchTray />
            </div>
          </Panel>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel>
            <PanelHead title="Throughput vs. batch size" sub="per worker — grounded in inference_ms(N) = (4.0 + 0.35·N)·scale" />
            <div className="p-3">
              <TimeSeries
                data={curve}
                series={[{ key: "throughput", color: "#ee4c2c", label: "req/s", kind: "area" }]}
                yUnit=" rps"
                yWidth={44}
              />
              <p className="px-1 pt-1 text-2xs text-fg-faint">
                X axis = batch size (1→64). Throughput rises fast then flattens as the per-item term
                (0.35·N) overtakes the fixed 4.0 ms overhead — the law that sets a sensible MAX_BATCH_SIZE.
              </p>
            </div>
          </Panel>
          <Panel>
            <PanelHead title="Live throughput & batch size" />
            <div className="p-3">
              <TimeSeries
                data={h}
                series={[
                  { key: "rps", color: "#ee4c2c", label: "served rps", kind: "area" },
                  { key: "avgBatch", color: "#58a6ff", label: "avg batch" },
                ]}
              />
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
