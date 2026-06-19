import { useState } from "react";
import clsx from "clsx";
import { motion } from "framer-motion";
import { ArrowRight, Check, RotateCcw } from "lucide-react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Badge, CodeBlock, Panel, PanelHead, PageHeader, Stat } from "@/components/primitives";
import { OPT_STEPS } from "@/sim/content";
import { fmtCompact, fmtMs } from "@/lib/format";

export default function OptimizationJourney() {
  const [step, setStep] = useState(0);
  const cur = OPT_STEPS[step];
  const prev = step > 0 ? OPT_STEPS[step - 1] : null;
  const first = OPT_STEPS[0];

  const data = OPT_STEPS.map((s, i) => ({
    name: s.label.replace(/^\+ /, ""),
    rps: s.rps,
    active: i <= step,
    isCur: i === step,
  }));

  const deltaPct = prev ? Math.round(((cur.rps - prev.rps) / prev.rps) * 100) : 0;
  const totalMul = (cur.rps / first.rps).toFixed(1);

  return (
    <div>
      <PageHeader
        title="Optimization Journey"
        desc="From a naive FastAPI handler to a production-shaped server, one optimization at a time. Watch throughput climb and latency stabilize at each step. Dynamic batching is the inflection point (measured 4.4× in docs/BENCHMARKS.md)."
        source="docs/BENCHMARKS.md · OPT_STEPS"
        right={
          <div className="flex gap-1.5">
            <button className="btn" onClick={() => setStep(0)}>
              <RotateCcw className="h-3.5 w-3.5" /> Restart
            </button>
            <button
              className="btn btn-accent"
              disabled={step >= OPT_STEPS.length - 1}
              onClick={() => setStep((s) => Math.min(OPT_STEPS.length - 1, s + 1))}
            >
              Next optimization <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        }
      />

      <div className="space-y-4 p-6">
        {/* stepper */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1">
          {OPT_STEPS.map((s, i) => (
            <button key={s.id} onClick={() => setStep(i)} className="flex shrink-0 items-center">
              <div
                className={clsx(
                  "flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
                  i === step
                    ? "border-torch/60 bg-torch/15 text-torch-soft"
                    : i < step
                      ? "border-ok/30 bg-ok/10 text-ok"
                      : "border-line bg-ink-800 text-fg-faint hover:text-fg-muted",
                )}
              >
                <span className={clsx("flex h-4 w-4 items-center justify-center rounded-full text-[9px]", i < step ? "bg-ok/20" : i === step ? "bg-torch/20" : "bg-ink-700")}>
                  {i < step ? <Check className="h-2.5 w-2.5" /> : i + 1}
                </span>
                {s.label.replace(/^\+ /, "")}
              </div>
              {i < OPT_STEPS.length - 1 && <div className="mx-0.5 h-px w-3 bg-line" />}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* metrics */}
          <div className="space-y-4 lg:col-span-2">
            <Panel>
              <PanelHead
                title={<span className="flex items-center gap-2">Step {step + 1}: {cur.label}</span>}
                right={
                  <div className="flex items-center gap-2">
                    {prev && <Badge tone={deltaPct >= 0 ? "ok" : "danger"}>{deltaPct >= 0 ? "+" : ""}{deltaPct}% rps</Badge>}
                    <Badge tone="torch">{totalMul}× vs naive</Badge>
                  </div>
                }
              />
              <div className="grid grid-cols-2 gap-4 p-4 md:grid-cols-3 lg:grid-cols-6">
                <Stat label="Throughput" value={`${fmtCompact(cur.rps)}/s`} tone="torch" />
                <Stat label="p50" value={fmtMs(cur.p50)} />
                <Stat label="p95" value={fmtMs(cur.p95)} tone="warn" />
                <Stat label="p99" value={fmtMs(cur.p99)} tone="warn" />
                <Stat label="Memory" value={`${Math.round(cur.memMul * 100)}%`} />
                <Stat label="Device util" value={`${Math.round(cur.util * 100)}%`} tone="ok" />
              </div>
            </Panel>

            <Panel>
              <PanelHead title="Throughput across the journey" sub="req/s — bars light up as you progress" />
              <div className="p-4">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={data} margin={{ top: 18, left: 0, right: 0 }}>
                    <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#677386" }} interval={0} axisLine={false} tickLine={false} angle={-18} textAnchor="end" height={50} />
                    <YAxis tick={{ fontSize: 10, fill: "#677386" }} axisLine={false} tickLine={false} tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)} />
                    <Bar dataKey="rps" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                      <LabelList dataKey="rps" position="top" style={{ fill: "#9aa7b8", fontSize: 9, fontFamily: "JetBrains Mono" }} formatter={(v: number) => fmtCompact(v)} />
                      {data.map((d, i) => (
                        <Cell key={i} fill={d.isCur ? "#ee4c2c" : d.active ? "#ee4c2c66" : "#222a38"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>

          {/* current step detail */}
          <Panel>
            <PanelHead title="What changed" />
            <div className="space-y-4 p-4">
              <CodeBlock>{cur.code}</CodeBlock>
              <motion.div key={cur.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="rounded-md border border-line bg-ink-900 p-3">
                <div className="text-2xs font-semibold uppercase tracking-wider text-fg-faint">Why it helps</div>
                <p className="mt-1.5 text-[13px] leading-relaxed text-fg-muted">{cur.insight}</p>
              </motion.div>
              {cur.id === "batching" && (
                <div className="rounded-md border border-torch/30 bg-torch/10 p-3 text-2xs leading-relaxed text-torch-soft">
                  This is the inflection point: a 4.3× jump from one change. Everything before tuned a single request;
                  batching changes the <em>unit of work</em> from 1 to 32.
                </div>
              )}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
