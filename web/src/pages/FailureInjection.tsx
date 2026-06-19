import clsx from "clsx";
import { motion } from "framer-motion";
import {
  Activity,
  Bug,
  CircleSlash,
  Database,
  PackageX,
  Skull,
  Waves,
  Zap,
} from "lucide-react";
import { Badge, Bar, Panel, PanelHead, PageHeader, Stat } from "@/components/primitives";
import { FlowDiagram } from "@/components/viz/FlowDiagram";
import { useSim } from "@/state/SimulationContext";
import { CIRCUIT_FAIL_THRESHOLD, JANITOR_STALE_AFTER_S, QUEUE_MAXLEN } from "@/sim/constants";
import type { FailureKind } from "@/sim/types";
import { fmtCompact, fmtPct } from "@/lib/format";

const FAILURES: { kind: FailureKind; label: string; icon: typeof Bug; desc: string; tone: string }[] = [
  { kind: "worker_crash", label: "Worker Crash", icon: Skull, desc: "Kill a worker mid-batch", tone: "danger" },
  { kind: "traffic_spike", label: "Traffic Spike", icon: Zap, desc: "8× sudden surge", tone: "warn" },
  { kind: "queue_overflow", label: "Queue Overflow", icon: Waves, desc: "Drive to 5000 RPS", tone: "warn" },
  { kind: "runtime_failure", label: "Runtime Failure", icon: Bug, desc: "Forward pass errors", tone: "danger" },
  { kind: "redis_failure", label: "Redis Failure", icon: Database, desc: "Data plane unreachable", tone: "danger" },
  { kind: "model_load_failure", label: "Model Load Fail", icon: PackageX, desc: "Version won't load", tone: "danger" },
];

export default function FailureInjection() {
  const { state, inject, clearFailure, clearAllFailures, setControls, start } = useSim();
  const active = state.activeFailures;

  const toggle = (k: FailureKind) => {
    if (active.has(k)) {
      clearFailure(k);
      if (k === "queue_overflow") setControls({ rps: 500 });
    } else {
      if (k === "queue_overflow") setControls({ rps: 5000 });
      inject(k);
      start();
    }
  };

  const deadWorker = state.workers.find((w) => !w.alive);

  return (
    <div>
      <PageHeader
        title="Failure Injection"
        desc="Inject faults and watch the platform's defenses respond: circuit breaker, backpressure/load-shedding, timeouts, and worker crash recovery via heartbeat + janitor re-queue."
        source="circuit_breaker.py · janitor.py · queues.py"
        right={
          <button className="btn" onClick={() => { clearAllFailures(); setControls({ rps: 500 }); }}>
            <CircleSlash className="h-3.5 w-3.5" /> Clear all
          </button>
        }
      />

      <div className="space-y-4 p-6">
        {/* injectors */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {FAILURES.map((f) => {
            const on = active.has(f.kind);
            return (
              <button
                key={f.kind}
                onClick={() => toggle(f.kind)}
                className={clsx(
                  "group rounded-lg border p-3 text-left transition-all",
                  on ? "border-danger/50 bg-danger/10" : "border-line bg-ink-800 hover:border-line-strong",
                )}
              >
                <div className="flex items-center justify-between">
                  <f.icon className={clsx("h-4 w-4", on ? "text-danger" : "text-fg-muted")} />
                  {on && <span className="h-1.5 w-1.5 rounded-full bg-danger animate-pulse-line" />}
                </div>
                <div className="mt-2 text-[13px] font-semibold text-fg">{f.label}</div>
                <div className="text-2xs text-fg-faint">{f.desc}</div>
              </button>
            );
          })}
        </div>

        {/* live flow + response */}
        <Panel>
          <PanelHead title="System response" sub="red tokens are requests being shed / failing" right={
            <div className="flex gap-3">
              <Stat label="served" value={`${fmtCompact(state.achievedRps)}/s`} tone="torch" />
              <Stat label="errors" value={fmtPct(state.errorRate, 1)} tone={state.errorRate > 0.05 ? "danger" : "ok"} />
            </div>
          } />
          <div className="p-4">
            <FlowDiagram />
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* circuit breaker */}
          <Panel>
            <PanelHead title="Circuit Breaker" sub="CLOSED → OPEN → HALF-OPEN" />
            <div className="space-y-4 p-4">
              <div className="flex items-center justify-between gap-2">
                {(["closed", "open", "half_open"] as const).map((st) => (
                  <div
                    key={st}
                    className={clsx(
                      "flex-1 rounded-md border px-2 py-3 text-center text-xs font-semibold transition-all",
                      state.circuit === st
                        ? st === "closed"
                          ? "border-ok/50 bg-ok/15 text-ok"
                          : st === "open"
                            ? "border-danger/50 bg-danger/15 text-danger"
                            : "border-warn/50 bg-warn/15 text-warn"
                        : "border-line bg-ink-900 text-fg-faint",
                    )}
                  >
                    {st.replace("_", "-")}
                    {state.circuit === st && (
                      <motion.div layoutId="cb" className="mx-auto mt-1 h-0.5 w-6 rounded-full bg-current" />
                    )}
                  </div>
                ))}
              </div>
              <div>
                <div className="mb-1 flex justify-between text-2xs text-fg-faint">
                  <span>failure count</span>
                  <span className="mono">{Math.round(state.circuitFailures)} / {CIRCUIT_FAIL_THRESHOLD}</span>
                </div>
                <Bar value={state.circuitFailures / CIRCUIT_FAIL_THRESHOLD} tone="danger" />
              </div>
              <p className="text-2xs leading-relaxed text-fg-faint">
                After {CIRCUIT_FAIL_THRESHOLD} failures the breaker OPENs and fast-fails requests with 503 for 10s,
                then HALF-OPENs to probe. Try <span className="text-fg-muted">Runtime Failure</span> or{" "}
                <span className="text-fg-muted">Redis Failure</span>.
              </p>
            </div>
          </Panel>

          {/* backpressure */}
          <Panel>
            <PanelHead title="Backpressure" sub={`ingest queue vs QUEUE_MAXLEN`} />
            <div className="space-y-4 p-4">
              <Stat label="Queue depth" value={fmtCompact(state.queueDepth)} tone={state.queueDepth > QUEUE_MAXLEN * 0.6 ? "danger" : "torch"} />
              <div>
                <div className="mb-1 flex justify-between text-2xs text-fg-faint">
                  <span>fill</span>
                  <span className="mono">{fmtPct(state.queueDepth / QUEUE_MAXLEN, 1)} of {fmtCompact(QUEUE_MAXLEN)}</span>
                </div>
                <Bar value={state.queueDepth / QUEUE_MAXLEN} tone={state.queueDepth > QUEUE_MAXLEN * 0.8 ? "danger" : "warn"} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Stat label="Shed (503) total" value={fmtCompact(state.totals.shed)} tone="danger" />
                <Stat label="Error rate" value={fmtPct(state.errorRate, 1)} tone={state.errorRate > 0.05 ? "danger" : "ok"} />
              </div>
              <p className="text-2xs leading-relaxed text-fg-faint">
                When the queue hits its cap the gateway returns 503 rather than letting the backlog grow unbounded —
                bounding tail latency for the requests it does accept.
              </p>
            </div>
          </Panel>

          {/* worker crash recovery */}
          <Panel>
            <PanelHead title="Worker Crash Recovery" sub="heartbeat → janitor re-queue" />
            <div className="space-y-2.5 p-4">
              {[
                { k: "crash", label: "Worker crashes mid-batch", done: !!deadWorker || state.events.some((e) => e.message.includes("crashed")) },
                { k: "strand", label: "Batch stranded in processing list", done: !!deadWorker?.strandedBatch },
                { k: "timeout", label: `Heartbeat stale (${JANITOR_STALE_AFTER_S}s)`, active: !!deadWorker, prog: deadWorker ? deadWorker.heartbeatAgeS / JANITOR_STALE_AFTER_S : 0 },
                { k: "requeue", label: "Janitor re-queues the batch", done: state.events.some((e) => e.message.includes("re-queued")) },
                { k: "recover", label: "Worker rejoins, request succeeds", done: state.events.some((e) => e.message.includes("recovered")) },
              ].map((s) => (
                <div key={s.k} className="flex items-center gap-2.5">
                  <span
                    className={clsx(
                      "flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px]",
                      s.done ? "bg-ok/20 text-ok" : "active" in s && s.active ? "bg-warn/20 text-warn" : "bg-ink-700 text-fg-faint",
                    )}
                  >
                    {s.done ? "✓" : "·"}
                  </span>
                  <span className={clsx("flex-1 text-2xs", s.done ? "text-fg-muted" : "text-fg-faint")}>{s.label}</span>
                  {"prog" in s && s.active && (
                    <span className="mono text-2xs text-warn">{(deadWorker!.heartbeatAgeS).toFixed(0)}s</span>
                  )}
                </div>
              ))}
              {deadWorker && (
                <div className="pt-1">
                  <Bar value={deadWorker.heartbeatAgeS / JANITOR_STALE_AFTER_S} tone="warn" />
                </div>
              )}
              <button className="btn mt-1 w-full text-2xs" onClick={() => { inject("worker_crash"); start(); }}>
                <Skull className="h-3 w-3" /> Crash a worker
              </button>
            </div>
          </Panel>
        </div>

        {/* event log */}
        <Panel>
          <PanelHead title="Event log" sub="emitted by the engine — same events the services would log" right={<Activity className="h-3.5 w-3.5 text-fg-faint" />} />
          <div className="max-h-64 overflow-y-auto p-2">
            {state.events.length === 0 && (
              <div className="px-2 py-6 text-center text-2xs text-fg-faint">No events yet — inject a failure to see the system react.</div>
            )}
            {state.events.map((e, i) => (
              <div key={i} className="flex items-center gap-3 border-b border-line/40 px-2 py-1.5 text-2xs last:border-0">
                <span className="mono w-12 shrink-0 text-fg-faint">{e.t.toFixed(1)}s</span>
                <Badge tone={e.level === "danger" ? "danger" : e.level === "warn" ? "warn" : e.level === "ok" ? "ok" : "default"}>{e.source}</Badge>
                <span className="text-fg-muted">{e.message}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
