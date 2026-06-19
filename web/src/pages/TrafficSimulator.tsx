import clsx from "clsx";
import { Panel, PanelHead, PageHeader, MetricCard, LegendDot, Bar } from "@/components/primitives";
import { TimeSeries } from "@/components/viz/TimeSeries";
import { useSim } from "@/state/SimulationContext";
import { RPS_PRESETS } from "@/sim/constants";
import { fmtCompact, fmtMs, fmtPct } from "@/lib/format";

export default function TrafficSimulator() {
  const { state, setControls, start } = useSim();
  const h = state.history;

  const setRps = (rps: number) => {
    setControls({ rps });
    start();
  };

  return (
    <div>
      <PageHeader
        title="Traffic Simulator"
        desc="Drive the platform at fixed request rates and watch queue depth, worker activity and latency evolve. At high RPS the queue grows until workers (or backpressure) catch up."
        source="SchedulerLoop · WorkerLoop"
        right={
          <div className="flex gap-1.5">
            {RPS_PRESETS.map((r) => (
              <button
                key={r}
                onClick={() => setRps(r)}
                className={clsx(
                  "btn px-2.5 text-xs mono",
                  state.controls.rps === r && "btn-accent",
                )}
              >
                {fmtCompact(r)} RPS
              </button>
            ))}
          </div>
        }
      />

      <div className="space-y-4 p-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          <MetricCard label="Offered" value={fmtCompact(state.offeredRps)} unit="rps" tone="default" series={h.map((d) => d.offered).slice(-40)} />
          <MetricCard label="Served" value={fmtCompact(state.achievedRps)} unit="rps" tone="torch" series={h.map((d) => d.rps).slice(-40)} />
          <MetricCard label="Queue Depth" value={fmtCompact(state.queueDepth)} tone={state.queueDepth > 2000 ? "danger" : "default"} series={h.map((d) => d.queueDepth).slice(-40)} />
          <MetricCard label="p99" value={fmtMs(state.p99)} tone="warn" series={h.map((d) => d.p99).slice(-40)} />
          <MetricCard label="Error Rate" value={fmtPct(state.errorRate, 1)} tone={state.errorRate > 0.05 ? "danger" : "ok"} series={h.map((d) => d.errorRate).slice(-40)} />
          <MetricCard label="Util" value={fmtPct(state.meanUtil)} tone={state.meanUtil > 0.9 ? "warn" : "ok"} series={h.map((d) => d.utilization).slice(-40)} />
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel>
            <PanelHead title="Incoming vs. served" sub="the gap is what queues (or sheds)" right={<div className="flex gap-3"><LegendDot color="#677386" label="offered" /><LegendDot color="#ee4c2c" label="served" /></div>} />
            <div className="p-3">
              <TimeSeries data={h} series={[{ key: "offered", color: "#677386", label: "offered", dashed: true }, { key: "rps", color: "#ee4c2c", label: "served", kind: "area" }]} yUnit=" rps" />
            </div>
          </Panel>
          <Panel>
            <PanelHead title="Queue depth" sub="backlog waiting for a worker" right={<LegendDot color="#a371f7" label="depth" />} />
            <div className="p-3">
              <TimeSeries data={h} series={[{ key: "queueDepth", color: "#a371f7", label: "queue", kind: "area" }]} />
            </div>
          </Panel>
          <Panel>
            <PanelHead title="Latency evolution" sub="p50 / p95 / p99 (ms)" right={<div className="flex gap-3"><LegendDot color="#58a6ff" label="p50" /><LegendDot color="#d29922" label="p95" /><LegendDot color="#f85149" label="p99" /></div>} />
            <div className="p-3">
              <TimeSeries data={h} series={[{ key: "p50", color: "#58a6ff", label: "p50" }, { key: "p95", color: "#d29922", label: "p95" }, { key: "p99", color: "#f85149", label: "p99" }]} yUnit="ms" />
            </div>
          </Panel>
          <Panel>
            <PanelHead title="Worker activity" sub={`${state.workers.filter((w) => w.alive).length} workers · ${state.controls.runtime}`} />
            <div className="space-y-2.5 p-4">
              {state.workers.map((w) => (
                <div key={w.id} className="flex items-center gap-3">
                  <span className={clsx("mono w-24 shrink-0 text-2xs", w.alive ? "text-fg-muted" : "text-danger line-through")}>{w.id}</span>
                  <Bar value={w.utilization} tone={w.utilization > 0.9 ? "warn" : "torch"} />
                  <span className="mono w-10 shrink-0 text-right text-2xs text-fg-faint">{fmtPct(w.utilization)}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
