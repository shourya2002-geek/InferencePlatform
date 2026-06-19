import clsx from "clsx";
import { motion } from "framer-motion";
import { Cpu, Skull } from "lucide-react";
import { Bar, Panel, PanelHead, PageHeader, Stat, Badge, MetricCard } from "@/components/primitives";
import { TimeSeries } from "@/components/viz/TimeSeries";
import { useSim } from "@/state/SimulationContext";
import { WORKER_PRESETS, capacityFor, inferenceMs, RUNTIMES } from "@/sim/constants";
import { fmtCompact, fmtMs, fmtPct } from "@/lib/format";

export default function WorkerPool() {
  const { state, setControls, start, inject } = useSim();
  const c = state.controls;
  const cap = capacityFor(c.modelVersion);
  const runtimeMul = RUNTIMES.find((r) => r.id === c.runtime)?.latencyMul ?? 1;
  const perWorker = (c.maxBatchSize * 1000) / (inferenceMs(c.batchingEnabled ? c.maxBatchSize : 1, cap) * runtimeMul);
  const alive = state.workers.filter((w) => w.alive).length;
  const totalCapacity = alive * perWorker;
  const h = state.history;

  return (
    <div>
      <PageHeader
        title="Worker Pool"
        desc="Workers are separated from the API layer so the expensive tier (the accelerator) scales independently. Each worker pulls a batch, runs one forward pass, and reports utilization. Add workers to shrink the queue."
        source="services/inference_worker"
        right={
          <div className="flex gap-1.5">
            {WORKER_PRESETS.map((w) => (
              <button key={w} onClick={() => { setControls({ workers: w }); start(); }} className={clsx("btn px-3 mono", c.workers === w && "btn-accent")}>
                {w}
              </button>
            ))}
          </div>
        }
      />

      <div className="space-y-4 p-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard label="Pool size" value={`${alive}/${state.workers.length}`} tone={alive < state.workers.length ? "warn" : "ok"} />
          <MetricCard label="Per-worker cap" value={fmtCompact(perWorker)} unit="rps" tone="info" hint={`batch ${c.batchingEnabled ? c.maxBatchSize : 1}`} />
          <MetricCard label="Pool capacity" value={fmtCompact(totalCapacity)} unit="rps" tone="torch" hint={`${alive}× workers`} />
          <MetricCard label="Headroom" value={fmtPct(Math.max(0, 1 - state.offeredRps / Math.max(1, totalCapacity)))} tone={state.offeredRps > totalCapacity ? "danger" : "ok"} hint={`offered ${fmtCompact(state.offeredRps)}`} />
        </div>

        <Panel>
          <PanelHead
            title="Worker grid"
            sub={`runtime: ${c.runtime} · model resnet:${c.modelVersion}`}
            right={<button className="btn text-2xs" onClick={() => inject("worker_crash")}><Skull className="h-3 w-3" /> crash one</button>}
          />
          <div className="grid grid-cols-2 gap-3 p-4 md:grid-cols-3 xl:grid-cols-4">
            {state.workers.map((w) => (
              <motion.div
                key={w.id}
                layout
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                className={clsx(
                  "rounded-lg border p-3",
                  w.alive ? "border-line bg-ink-800" : "border-danger/40 bg-danger/5",
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-fg">
                    {w.alive ? <Cpu className="h-3.5 w-3.5 text-torch" /> : <Skull className="h-3.5 w-3.5 text-danger" />}
                    <span className="mono">{w.id}</span>
                  </span>
                  <Badge tone={w.alive ? "ok" : "danger"}>{w.alive ? "alive" : "down"}</Badge>
                </div>
                <div className="mt-3">
                  <div className="mb-1 flex justify-between text-2xs text-fg-faint">
                    <span>utilization</span>
                    <span className="mono">{fmtPct(w.utilization)}</span>
                  </div>
                  <Bar value={w.utilization} tone={w.utilization > 0.9 ? "warn" : "torch"} />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-2xs">
                  <div><div className="text-fg-faint">batches</div><div className="mono text-fg">{Math.round(w.batchesProcessed)}</div></div>
                  <div><div className="text-fg-faint">last batch</div><div className="mono text-fg">{w.lastBatchSize}</div></div>
                  <div><div className="text-fg-faint">infer</div><div className="mono text-fg">{w.alive ? fmtMs(w.lastInferenceMs) : "—"}</div></div>
                  <div><div className="text-fg-faint">{w.alive ? "heartbeat" : "stale"}</div><div className={clsx("mono", w.alive ? "text-ok" : "text-danger")}>{w.alive ? "ok" : `${w.heartbeatAgeS.toFixed(0)}s`}</div></div>
                </div>
                {!w.alive && w.strandedBatch != null && (
                  <div className="mt-2 rounded border border-danger/30 bg-danger/10 px-2 py-1 text-2xs text-danger">
                    {w.strandedBatch} requests stranded — janitor re-queues at 10s
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel>
            <PanelHead title="Queue depth vs. pool size" sub="more workers → faster drain" right={<Stat label="now" value={fmtCompact(state.queueDepth)} />} />
            <div className="p-3">
              <TimeSeries data={h} series={[{ key: "queueDepth", color: "#a371f7", label: "queue", kind: "area" }]} />
            </div>
          </Panel>
          <Panel>
            <PanelHead title="Throughput & utilization" />
            <div className="p-3">
              <TimeSeries data={h} series={[{ key: "rps", color: "#ee4c2c", label: "served rps", kind: "area" }]} />
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
