import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { Panel, PanelHead, PageHeader, LegendDot, Badge } from "@/components/primitives";
import { TimeSeries } from "@/components/viz/TimeSeries";
import { useSim } from "@/state/SimulationContext";
import { METRIC_NAMES } from "@/sim/constants";
import { fmtMs } from "@/lib/format";

const STAGES = ["gateway", "redis", "scheduler", "worker", "response"];

interface Trace {
  id: string;
  startedAt: number;
  spanMs: number[]; // ms per stage
}

function TraceFlow() {
  const { state } = useSim();
  const [traces, setTraces] = useState<Trace[]>([]);
  const tRef = useRef(0);

  useEffect(() => {
    const h = setInterval(() => {
      if (!state.running) return;
      tRef.current += 0.25;
      // spawn a new trace, retire old ones
      setTraces((prev) => {
        const now = tRef.current;
        const next = prev.filter((tr) => now - tr.startedAt < 5);
        if (next.length < 5) {
          const q = state.latency.queueMs;
          next.push({
            id: Math.random().toString(16).slice(2, 10),
            startedAt: now,
            spanMs: [1.2, 0.4, Math.max(0.5, state.latency.batchWaitMs), state.latency.inferenceMs, 0.3 + q * 0.0],
          });
        }
        return next;
      });
    }, 250);
    return () => clearInterval(h);
  }, [state.running, state.latency]);

  return (
    <div className="space-y-2 p-3">
      {/* stage header */}
      <div className="flex items-center gap-2 pl-20 pr-2 text-2xs text-fg-faint">
        {STAGES.map((s) => (
          <div key={s} className="flex-1 text-center">{s}</div>
        ))}
      </div>
      {traces.length === 0 && <div className="px-2 py-6 text-center text-2xs text-fg-faint">Start the simulation to watch traces propagate.</div>}
      {traces.map((tr) => {
        const elapsed = tRef.current - tr.startedAt;
        const prog = Math.min(1, elapsed / 2.4);
        return (
          <div key={tr.id} className="flex items-center gap-2">
            <span className="mono w-16 shrink-0 truncate text-2xs text-info">{tr.id}</span>
            <div className="relative flex h-5 flex-1 items-center overflow-hidden rounded border border-line bg-ink-900">
              {STAGES.map((_, i) => (
                <div key={i} className="h-full flex-1 border-r border-line/40 last:border-0" />
              ))}
              <div
                className="absolute h-2 w-2 rounded-full bg-torch transition-all duration-200"
                style={{ left: `calc(${prog * 100}% - 4px)`, boxShadow: "0 0 8px #ee4c2c" }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Observability() {
  const { state } = useSim();
  const h = state.history;

  return (
    <div>
      <PageHeader
        title="Observability"
        desc="Grafana-style view of the platform's Prometheus metrics, all emitted by the running services. A single trace_id threads across the Redis hops so logs, metrics and traces correlate."
        source="prometheus_client · observability/metrics.py"
        right={
          <div className="flex gap-1.5">
            <Badge tone="ok">scrape 5s</Badge>
            <Badge tone="info">OTLP traces</Badge>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-2 xl:grid-cols-3">
        <ChartPanel title="Request Rate" metric={METRIC_NAMES.requestCount} legend={[["#677386", "offered"], ["#ee4c2c", "served"]]}>
          <TimeSeries data={h} height={150} series={[{ key: "offered", color: "#677386", label: "offered", dashed: true }, { key: "rps", color: "#ee4c2c", label: "served", kind: "area" }]} />
        </ChartPanel>

        <ChartPanel title="Latency (p50/p95/p99)" metric={METRIC_NAMES.requestLatency} legend={[["#58a6ff", "p50"], ["#d29922", "p95"], ["#f85149", "p99"]]}>
          <TimeSeries data={h} height={150} yUnit="ms" series={[{ key: "p50", color: "#58a6ff", label: "p50" }, { key: "p95", color: "#d29922", label: "p95" }, { key: "p99", color: "#f85149", label: "p99" }]} />
        </ChartPanel>

        <ChartPanel title="Queue Depth" metric={METRIC_NAMES.queueDepth} legend={[["#a371f7", "ingest"], ["#2dd4bf", "batch q"]]}>
          <TimeSeries data={h} height={150} series={[{ key: "queueDepth", color: "#a371f7", label: "ingest", kind: "area" }, { key: "batchQueueDepth", color: "#2dd4bf", label: "batch q" }]} />
        </ChartPanel>

        <ChartPanel title="Batch Size" metric={METRIC_NAMES.batchSize} legend={[["#58a6ff", "avg batch"]]}>
          <TimeSeries data={h} height={150} series={[{ key: "avgBatch", color: "#58a6ff", label: "avg batch", kind: "area" }]} domainMax={64} />
        </ChartPanel>

        <ChartPanel title="Worker Utilization" metric={METRIC_NAMES.workerUtil} legend={[["#3fb950", "mean util"]]}>
          <TimeSeries data={h.map((d) => ({ ...d, utilPct: Math.round(d.utilization * 100) }))} height={150} yUnit="%" series={[{ key: "utilPct", color: "#3fb950", label: "util %", kind: "area" }]} domainMax={100} />
        </ChartPanel>

        <ChartPanel title="Error Rate" metric={METRIC_NAMES.requestCount + '{status!="ok"}'} legend={[["#f85149", "503/504 rps"]]}>
          <TimeSeries data={h} height={150} series={[{ key: "shed503", color: "#f85149", label: "shed/s", kind: "area" }]} />
        </ChartPanel>

        <Panel className="xl:col-span-2">
          <PanelHead title="Trace flow" sub="trace_id propagating Gateway → Redis → Scheduler → Worker → Response" right={<span className="mono text-2xs text-fg-faint">infer {fmtMs(state.latency.inferenceMs)}</span>} />
          <TraceFlow />
        </Panel>

        <Panel>
          <PanelHead title="Exported metrics" />
          <div className="space-y-1.5 p-3">
            {Object.values(METRIC_NAMES).map((m) => (
              <div key={m} className="truncate rounded border border-line bg-ink-900 px-2 py-1.5">
                <code className="mono text-2xs text-info">{m}</code>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function ChartPanel({
  title,
  metric,
  legend,
  children,
}: {
  title: string;
  metric: string;
  legend: [string, string][];
  children: React.ReactNode;
}) {
  return (
    <Panel>
      <PanelHead
        title={title}
        sub={<code className="mono text-[10px] text-fg-faint">{metric}</code>}
        right={<div className="flex gap-2">{legend.map(([c, l]) => <LegendDot key={l} color={c} label={l} />)}</div>}
      />
      <div className={clsx("p-3")}>{children}</div>
    </Panel>
  );
}
