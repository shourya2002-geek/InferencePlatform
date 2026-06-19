import { useState } from "react";
import clsx from "clsx";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Panel, PanelHead, PageHeader } from "@/components/primitives";
import { RUNTIMES, capacityFor, inferenceMs } from "@/sim/constants";
import { fmtCompact, fmtMs } from "@/lib/format";

const BATCH = 16;
const cap = capacityFor("v2");
const baseMs = inferenceMs(BATCH, cap); // eager baseline at batch 16

interface Row {
  id: string;
  label: string;
  implemented: boolean;
  latency: number;
  throughput: number;
  memory: number;
  modelSize: number;
  startup: number;
  note: string;
}

const ROWS: Row[] = RUNTIMES.map((r) => {
  const latency = baseMs * r.latencyMul;
  return {
    id: r.id,
    label: r.label,
    implemented: r.implemented,
    latency,
    throughput: (BATCH * 1000) / latency,
    memory: r.memMul,
    modelSize: r.modelSizeMul,
    startup: r.startupMs,
    note: r.note,
  };
});

const METRICS = [
  { id: "throughput", label: "Throughput (req/s)", fmt: (r: Row) => fmtCompact(r.throughput), val: (r: Row) => r.throughput, better: "high", color: "#ee4c2c" },
  { id: "latency", label: "Latency (ms, batch 16)", fmt: (r: Row) => fmtMs(r.latency), val: (r: Row) => r.latency, better: "low", color: "#58a6ff" },
  { id: "memory", label: "Memory (relative)", fmt: (r: Row) => `${Math.round(r.memory * 100)}%`, val: (r: Row) => r.memory, better: "low", color: "#a371f7" },
  { id: "modelSize", label: "Model size (relative)", fmt: (r: Row) => `${Math.round(r.modelSize * 100)}%`, val: (r: Row) => r.modelSize, better: "low", color: "#2dd4bf" },
  { id: "startup", label: "Startup cost (ms)", fmt: (r: Row) => fmtMs(r.startup), val: (r: Row) => r.startup, better: "low", color: "#d29922" },
] as const;

export default function RuntimeComparison() {
  const [metric, setMetric] = useState<(typeof METRICS)[number]>(METRICS[0]);
  const chartData = [...ROWS].sort((a, b) =>
    metric.better === "high" ? metric.val(b) - metric.val(a) : metric.val(a) - metric.val(b),
  );

  return (
    <div>
      <PageHeader
        title="Runtime Comparison"
        desc="Latency, throughput, memory, model size and startup cost across runtimes. stub / torch_eager / torchscript / onnx and the AMP & INT8 flags are implemented in the worker; torch.compile and BF16 are shown as representative for completeness."
        source="factory.build_backend · torch_backend.py"
        right={
          <select
            className="h-7 rounded-md border border-line bg-ink-750 px-2 text-xs text-fg"
            value={metric.id}
            onChange={(e) => setMetric(METRICS.find((m) => m.id === e.target.value)!)}
          >
            {METRICS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        }
      />

      <div className="space-y-4 p-6">
        <Panel>
          <PanelHead title={metric.label} sub={`lower is better → ${metric.better === "low" ? "yes" : "no (higher better)"}`} />
          <div className="p-4">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 24, right: 24 }}>
                <XAxis type="number" tick={{ fontSize: 10, fill: "#677386" }} axisLine={false} tickLine={false} tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)} />
                <YAxis type="category" dataKey="label" width={110} tick={{ fontSize: 11, fill: "#9aa7b8" }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "#11151d", border: "1px solid #2b3544", borderRadius: 8 }}
                  formatter={(v: number) => metric.fmt({ [metric.id]: v } as unknown as Row)}
                  cursor={{ fill: "#ffffff08" }}
                />
                <Bar dataKey={metric.id} radius={[0, 3, 3, 0]} isAnimationActive={false}>
                  {chartData.map((r) => (
                    <Cell key={r.id} fill={r.implemented ? metric.color : "#33405288"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="px-1 pt-1 text-2xs text-fg-faint">
              Solid bars are runtimes implemented in the repo; muted bars are representative.
            </p>
          </div>
        </Panel>

        <Panel>
          <PanelHead title="Full comparison" sub="relative to PyTorch Eager at batch 16, resnet:v2" />
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-line text-2xs uppercase tracking-wider text-fg-faint">
                  <th className="px-4 py-2 text-left">Runtime</th>
                  <th className="px-3 py-2 text-right">Latency</th>
                  <th className="px-3 py-2 text-right">Throughput</th>
                  <th className="px-3 py-2 text-right">Memory</th>
                  <th className="px-3 py-2 text-right">Model size</th>
                  <th className="px-3 py-2 text-right">Startup</th>
                  <th className="px-4 py-2 text-left">Notes</th>
                </tr>
              </thead>
              <tbody>
                {ROWS.map((r) => (
                  <tr key={r.id} className="border-b border-line/60 hover:bg-ink-800/50">
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-fg">{r.label}</span>
                        {r.implemented ? <Badge tone="ok">in repo</Badge> : <Badge tone="default">repr.</Badge>}
                      </div>
                    </td>
                    <td className="mono px-3 py-2.5 text-right text-info">{fmtMs(r.latency)}</td>
                    <td className="mono px-3 py-2.5 text-right text-torch-soft">{fmtCompact(r.throughput)}/s</td>
                    <td className="mono px-3 py-2.5 text-right text-fg-muted">{Math.round(r.memory * 100)}%</td>
                    <td className="mono px-3 py-2.5 text-right text-fg-muted">{Math.round(r.modelSize * 100)}%</td>
                    <td className="mono px-3 py-2.5 text-right text-warn">{fmtMs(r.startup)}</td>
                    <td className="px-4 py-2.5 text-2xs text-fg-faint">{r.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Insight title="Startup vs. speed" tone="warn" body="TorchScript and torch.compile pay a one-time compile cost (480ms / ~5s) to win steady-state latency. Worth it for long-lived servers, painful for cold starts / serverless." />
          <Insight title="Quantization shrinks too" tone="violet" body="INT8 dynamic quantization cuts model size to ~27% and memory to ~40% with a CPU speedup — ideal when the bottleneck is CPU Linear layers." />
          <Insight title="ONNX for portability" tone="info" body="ONNX Runtime is often the fastest CPU path and runs the same graph across CPU/CUDA/TensorRT execution providers." />
        </div>
      </div>
    </div>
  );
}

function Insight({ title, body, tone }: { title: string; body: string; tone: "warn" | "violet" | "info" }) {
  const ring = { warn: "border-warn/30", violet: "border-violet/30", info: "border-info/30" }[tone];
  return (
    <div className={clsx("rounded-lg border bg-ink-800 p-4", ring)}>
      <div className="text-[13px] font-semibold text-fg">{title}</div>
      <p className="mt-1 text-2xs leading-relaxed text-fg-muted">{body}</p>
    </div>
  );
}
