import { useNavigate } from "react-router-dom";
import { MetricCard, Panel, PanelHead, PageHeader, Badge, LegendDot } from "@/components/primitives";
import { FlowDiagram } from "@/components/viz/FlowDiagram";
import { TimeSeries } from "@/components/viz/TimeSeries";
import { useSim } from "@/state/SimulationContext";
import { fmtCompact, fmtMs, fmtPct } from "@/lib/format";

function tail(arr: number[], n = 40): number[] {
  return arr.slice(-n);
}

export default function Overview() {
  const { state } = useSim();
  const nav = useNavigate();
  const h = state.history;
  const col = {
    rps: h.map((d) => d.rps),
    q: h.map((d) => d.queueDepth),
    batch: h.map((d) => d.avgBatch),
    p50: h.map((d) => d.p50),
    p95: h.map((d) => d.p95),
    p99: h.map((d) => d.p99),
    err: h.map((d) => d.errorRate),
    util: h.map((d) => d.utilization),
  };
  const aliveWorkers = state.workers.filter((w) => w.alive).length;

  return (
    <div>
      <PageHeader
        title="Platform Overview"
        desc="Live health of the inference serving platform. Every number is produced by the grounded simulation engine — the same batching, queueing and runtime economics as the Python services."
        source="all services"
        right={
          <div className="flex items-center gap-2">
            <Badge tone={state.circuit === "closed" ? "ok" : state.circuit === "open" ? "danger" : "warn"}>
              circuit: {state.circuit}
            </Badge>
            <Badge tone={state.controls.batchingEnabled ? "torch" : "default"}>
              batch ≤ {state.controls.maxBatchSize}
            </Badge>
            <Badge tone="info">{state.controls.runtime}</Badge>
          </div>
        }
      />

      <div className="space-y-4 p-6">
        {/* KPI cards */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          <MetricCard label="Requests / sec" value={fmtCompact(state.achievedRps)} tone="torch" series={tail(col.rps)} hint={`offered ${fmtCompact(state.offeredRps)}`} />
          <MetricCard label="Queue Depth" value={fmtCompact(state.queueDepth)} tone={state.queueDepth > 2000 ? "danger" : "default"} series={tail(col.q)} />
          <MetricCard label="Active Workers" value={`${aliveWorkers}/${state.workers.length}`} tone={aliveWorkers < state.workers.length ? "warn" : "ok"} />
          <MetricCard label="Avg Batch Size" value={state.avgBatchSize.toFixed(1)} tone="info" series={tail(col.batch)} hint={state.lastFlushReason === "MAX_BATCH_SIZE" ? "size flush" : state.lastFlushReason === "MAX_WAIT_MS" ? "timer flush" : "idle"} />
          <MetricCard label="Worker Util" value={fmtPct(state.meanUtil)} tone={state.meanUtil > 0.9 ? "warn" : "ok"} series={tail(col.util)} />
          <MetricCard label="p50 Latency" value={fmtMs(state.p50)} tone="default" series={tail(col.p50)} />
          <MetricCard label="p95 Latency" value={fmtMs(state.p95)} tone="warn" series={tail(col.p95)} />
          <MetricCard label="p99 Latency" value={fmtMs(state.p99)} tone={state.p99 > 1000 ? "danger" : "warn"} series={tail(col.p99)} />
          <MetricCard label="Error Rate" value={fmtPct(state.errorRate, 1)} tone={state.errorRate > 0.05 ? "danger" : "ok"} series={tail(col.err)} />
          <MetricCard label="GPU / Device" value={fmtPct(state.gpuUtil)} tone="violet" series={tail(col.util)} />
        </div>

        {/* Architecture flow */}
        <Panel>
          <PanelHead
            title="Request flow"
            sub="Client → Gateway → Redis → Scheduler → Batch Queue → Workers → Runtime → Response"
            right={
              <button className="text-2xs text-fg-faint hover:text-fg" onClick={() => nav("/architecture")}>
                open explorer →
              </button>
            }
          />
          <div className="p-4">
            <FlowDiagram onSelect={() => nav("/architecture")} />
          </div>
        </Panel>

        {/* charts */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel>
            <PanelHead
              title="Throughput"
              sub="offered vs. served req/s"
              right={
                <div className="flex gap-3">
                  <LegendDot color="#677386" label="offered" />
                  <LegendDot color="#ee4c2c" label="served" />
                </div>
              }
            />
            <div className="p-3">
              <TimeSeries
                data={h}
                series={[
                  { key: "offered", color: "#677386", label: "offered", kind: "line", dashed: true },
                  { key: "rps", color: "#ee4c2c", label: "served", kind: "area" },
                ]}
                yUnit=" rps"
              />
            </div>
          </Panel>
          <Panel>
            <PanelHead
              title="Latency percentiles"
              sub="end-to-end (ms)"
              right={
                <div className="flex gap-3">
                  <LegendDot color="#58a6ff" label="p50" />
                  <LegendDot color="#d29922" label="p95" />
                  <LegendDot color="#f85149" label="p99" />
                </div>
              }
            />
            <div className="p-3">
              <TimeSeries
                data={h}
                series={[
                  { key: "p50", color: "#58a6ff", label: "p50" },
                  { key: "p95", color: "#d29922", label: "p95" },
                  { key: "p99", color: "#f85149", label: "p99" },
                ]}
                yUnit="ms"
              />
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
