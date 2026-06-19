import { useEffect, useState } from "react";
import clsx from "clsx";
import { motion } from "framer-motion";
import { Bar, Badge, CodeBlock, Panel, PanelHead, PageHeader, Stat } from "@/components/primitives";
import { AUTOGRAD_MODES, PIPELINE_STAGES, TRAIN_EVAL } from "@/sim/content";
import { capacityFor, inferenceMs } from "@/sim/constants";
import { fmtMs, fmtCompact } from "@/lib/format";

const TABS = [
  { id: "A", label: "Train vs Eval" },
  { id: "B", label: "Autograd Overhead" },
  { id: "C", label: "GPU Utilization" },
  { id: "D", label: "Inference Pipeline" },
  { id: "E", label: "CUDA Timeline" },
];

export default function RuntimeLab() {
  const [tab, setTab] = useState("A");
  return (
    <div>
      <PageHeader
        title="PyTorch Runtime Lab"
        desc="The PyTorch-internals teaching section: how eval(), autograd contexts, batching, the preprocessing pipeline and CUDA's async execution model affect inference. Techniques mirror those applied in the worker's torch_backend."
        source="inference_worker/infrastructure/backends/torch_backend.py"
      />
      <div className="px-6 pt-4">
        <div className="flex gap-1 border-b border-line">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={clsx(
                "relative px-3 py-2 text-[13px] font-medium transition-colors",
                tab === t.id ? "text-fg" : "text-fg-faint hover:text-fg-muted",
              )}
            >
              <span className="mono mr-1.5 text-2xs text-torch-soft">{t.id}</span>
              {t.label}
              {tab === t.id && <span className="absolute inset-x-0 -bottom-px h-0.5 bg-torch" />}
            </button>
          ))}
        </div>
      </div>
      <div className="p-6">
        {tab === "A" && <ScenarioA />}
        {tab === "B" && <ScenarioB />}
        {tab === "C" && <ScenarioC />}
        {tab === "D" && <ScenarioD />}
        {tab === "E" && <ScenarioE />}
      </div>
    </div>
  );
}

/* ----------------------------------------------- A: train() vs eval() ----- */
function DropoutNet({ training }: { training: boolean }) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!training) return;
    const h = setInterval(() => setTick((t) => t + 1), 700);
    return () => clearInterval(h);
  }, [training]);
  const cols = [4, 6, 6, 3];
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-ink-900 p-4">
      {cols.map((n, ci) => (
        <div key={ci} className="flex flex-col gap-2">
          {Array.from({ length: n }).map((_, ni) => {
            const dropped = training && ci > 0 && ci < 3 && ((ni + tick + ci) * 7) % 10 < 4;
            return (
              <motion.div
                key={ni}
                className={clsx(
                  "h-3.5 w-3.5 rounded-full border",
                  dropped ? "border-line bg-ink-700" : "border-torch/50 bg-torch/60",
                )}
                animate={{ opacity: dropped ? 0.25 : 1, scale: dropped ? 0.85 : 1 }}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}

function ScenarioA() {
  const rows: [string, keyof typeof TRAIN_EVAL.train][] = [
    ["Dropout", "dropout"],
    ["BatchNorm", "batchnorm"],
    ["Autograd", "autograd"],
    ["Output", "determinism"],
  ];
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {(["train", "eval"] as const).map((mode) => (
        <Panel key={mode}>
          <PanelHead
            title={<code className="mono text-sm">model.{mode}()</code>}
            right={<Badge tone={mode === "eval" ? "ok" : "warn"}>{mode === "eval" ? "serving" : "training"}</Badge>}
          />
          <div className="space-y-4 p-4">
            <DropoutNet training={mode === "train"} />
            <div className="divide-y divide-line rounded-md border border-line">
              {rows.map(([label, key]) => (
                <div key={key} className="grid grid-cols-3 gap-2 px-3 py-2 text-[13px]">
                  <span className="font-medium text-fg-faint">{label}</span>
                  <span className="col-span-2 text-fg-muted">{TRAIN_EVAL[mode][key]}</span>
                </div>
              ))}
            </div>
          </div>
        </Panel>
      ))}
      <Panel className="lg:col-span-2">
        <PanelHead title="Why eval() is required before serving" />
        <div className="p-4 text-[13px] leading-relaxed text-fg-muted">
          In <code className="mono text-torch-soft">train()</code> mode dropout randomly zeroes activations and
          BatchNorm uses the current <em>batch</em> statistics — with batch size 1 (common in naive serving) those
          stats are garbage, producing unstable, non-deterministic predictions. The worker always calls{" "}
          <code className="mono text-info">module.eval()</code> at load time.
          <CodeBlock className="mt-3">{`module = build_module(...)
module.eval()                       # running BN stats, dropout = identity
# ... later, per request:
with torch.inference_mode():
    logits = module(x)`}</CodeBlock>
        </div>
      </Panel>
    </div>
  );
}

/* ------------------------------------------- B: autograd overhead --------- */
function ScenarioB() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {AUTOGRAD_MODES.map((m) => (
          <Panel key={m.id}>
            <PanelHead title={<code className="mono text-[13px]">{m.label}</code>} right={m.id !== "normal" ? <Badge tone="ok">serving</Badge> : undefined} />
            <div className="space-y-3 p-4">
              <GraphSchematic storeActivations={m.activations} grad={m.grad} />
              <Metric label="Memory" value={`${Math.round(m.memMul * 100)}%`} frac={m.memMul} tone="info" />
              <Metric label="Latency" value={`${Math.round(m.latMul * 100)}%`} frac={m.latMul} tone="torch" />
              <div className="grid grid-cols-3 gap-2 pt-1 text-2xs">
                <Flag on={m.graph} label="graph" />
                <Flag on={m.activations} label="activ." />
                <Flag on={m.grad} label="grad" />
              </div>
            </div>
          </Panel>
        ))}
      </div>
      <Panel>
        <PanelHead title="Autograd keeps a tape you don't need at inference" />
        <div className="p-4 text-[13px] leading-relaxed text-fg-muted">
          A normal forward pass records every op and stores intermediate activations so it can compute gradients on a
          backward pass. At inference there is no backward pass.{" "}
          <code className="mono text-info">torch.no_grad()</code> skips graph construction;{" "}
          <code className="mono text-info">torch.inference_mode()</code> goes further — it also drops version
          counters and view tracking, the strongest "no autograd" context.
          <CodeBlock className="mt-3">{`with torch.inference_mode():     # used by TorchBackend.infer()
    logits = module(x)            # no tape, no activation storage`}</CodeBlock>
        </div>
      </Panel>
    </div>
  );
}

function GraphSchematic({ storeActivations, grad }: { storeActivations: boolean; grad: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-md border border-line bg-ink-900 p-3">
      {["x", "conv", "bn", "relu", "fc"].map((n, i) => (
        <div key={n} className="flex flex-col items-center gap-1">
          <div className="flex h-8 w-8 items-center justify-center rounded border border-line bg-ink-700 text-2xs text-fg-muted mono">
            {n}
          </div>
          {storeActivations && i > 0 && i < 4 ? (
            <div className="h-1.5 w-1.5 rounded-full bg-violet" title="stored activation" />
          ) : (
            <div className="h-1.5 w-1.5" />
          )}
          {grad && i > 0 ? <div className="text-[8px] text-warn">∇</div> : <div className="text-[8px]">&nbsp;</div>}
        </div>
      ))}
    </div>
  );
}

function Flag({ on, label }: { on: boolean; label: string }) {
  return (
    <span className={clsx("flex items-center justify-center gap-1 rounded border px-1 py-0.5", on ? "border-warn/30 bg-warn/10 text-warn" : "border-ok/30 bg-ok/10 text-ok")}>
      {on ? "✓" : "✕"} {label}
    </span>
  );
}

function Metric({ label, value, frac, tone }: { label: string; value: string; frac: number; tone: "info" | "torch" }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-2xs">
        <span className="text-fg-faint">{label}</span>
        <span className="mono text-fg-muted">{value}</span>
      </div>
      <Bar value={frac} tone={tone} />
    </div>
  );
}

/* ------------------------------------------- C: GPU utilization ----------- */
function ScenarioC() {
  const cap = capacityFor("v2");
  const sizes = [1, 4, 16, 32, 64];
  const rows = sizes.map((b) => {
    const ms = inferenceMs(b, cap);
    const perItem = ms / b;
    const throughput = (b * 1000) / ms;
    const overheadShare = (4.0 * (cap / 96)) / ms;
    const occupancy = Math.min(1, 0.12 + Math.log2(b + 1) / 7);
    return { b, ms, perItem, throughput, overheadShare, occupancy };
  });
  const maxTp = Math.max(...rows.map((r) => r.throughput));
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHead title="Batch size sweep" sub="grounded in inference_ms(N) = (4.0 + 0.35·N)·scale (resnet:v2)" />
        <div className="overflow-x-auto p-4">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-2xs uppercase tracking-wider text-fg-faint">
                <th className="px-2 py-1.5 text-left">Batch</th>
                <th className="px-2 py-1.5 text-right">Forward</th>
                <th className="px-2 py-1.5 text-right">Per-item</th>
                <th className="px-2 py-1.5 text-right">Throughput</th>
                <th className="px-2 py-1.5 text-left">Kernel-launch overhead</th>
                <th className="px-2 py-1.5 text-left">GPU occupancy</th>
              </tr>
            </thead>
            <tbody className="mono">
              {rows.map((r) => (
                <tr key={r.b} className="border-t border-line">
                  <td className="px-2 py-2 font-semibold text-fg">{r.b}</td>
                  <td className="px-2 py-2 text-right text-fg-muted">{fmtMs(r.ms)}</td>
                  <td className="px-2 py-2 text-right text-torch-soft">{r.perItem.toFixed(2)}ms</td>
                  <td className="px-2 py-2 text-right text-fg">{fmtCompact(r.throughput)}/s</td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-28"><Bar value={r.overheadShare} tone="warn" /></div>
                      <span className="text-2xs text-fg-faint">{Math.round(r.overheadShare * 100)}%</span>
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-28"><Bar value={r.occupancy} tone="ok" /></div>
                      <span className="text-2xs text-fg-faint">{Math.round(r.occupancy * 100)}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Panel><div className="p-4"><Stat label="Best throughput" value={`${fmtCompact(maxTp)}/s`} tone="torch" /><p className="mt-2 text-2xs text-fg-faint">at batch 64 — per-item cost is lowest because the 4.0ms launch overhead is shared across 64 samples.</p></div></Panel>
        <Panel><div className="p-4"><Stat label="Batch-1 per-item" value={`${rows[0].perItem.toFixed(2)}ms`} tone="warn" /><p className="mt-2 text-2xs text-fg-faint">{Math.round(rows[0].overheadShare * 100)}% of a batch-1 forward pass is pure kernel-launch overhead — wasted.</p></div></Panel>
        <Panel><div className="p-4"><Stat label="Why batching exists" value="amortize launch" tone="ok" /><p className="mt-2 text-2xs text-fg-faint">A GPU launches one kernel per forward call regardless of N. Bigger N = the fixed cost is paid once for more useful work.</p></div></Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------- D: inference pipeline -------- */
function ScenarioD() {
  const total = PIPELINE_STAGES.reduce((a, s) => a + s.shareCpu, 0);
  const colorFor = (d: string) => (d === "gpu" ? "#ee4c2c" : d === "transfer" ? "#a371f7" : "#58a6ff");
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHead title="Latency contribution per stage" sub="Image decode → … → Forward pass → Post-process → Response" />
        <div className="p-4">
          <div className="flex h-9 w-full overflow-hidden rounded-md border border-line">
            {PIPELINE_STAGES.map((s) => (
              <div key={s.id} className="relative flex items-center justify-center" style={{ width: `${(s.shareCpu / total) * 100}%`, background: colorFor(s.device) + "33", borderRight: "1px solid #1e2733" }} title={`${s.label} — ${s.shareCpu}%`}>
                <span className="truncate px-1 text-[9px] font-medium text-fg-muted">{Math.round((s.shareCpu / total) * 100)}%</span>
              </div>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
            {PIPELINE_STAGES.map((s, i) => (
              <motion.div key={s.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }} className="flex items-center gap-3 rounded-md border border-line bg-ink-900 px-3 py-2">
                <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: colorFor(s.device) }} />
                <span className="w-32 shrink-0 text-[13px] font-medium text-fg">{s.label}</span>
                <span className="mono w-10 shrink-0 text-2xs text-fg-muted">{Math.round((s.shareCpu / total) * 100)}%</span>
                <span className="truncate text-2xs text-fg-faint">{s.note}</span>
              </motion.div>
            ))}
          </div>
          <p className="mt-3 text-2xs leading-relaxed text-fg-faint">
            The forward pass is only ~36% of the wall time — <span className="text-fg-muted">decode + preprocess (CPU)</span>{" "}
            is the silent cost people forget when they say "the model only takes 3ms". The worker offloads inference to a
            thread so the event loop stays responsive.
          </p>
        </div>
      </Panel>
    </div>
  );
}

/* ------------------------------------------- E: CUDA timeline ------------- */
function ScenarioE() {
  const [synced, setSynced] = useState(false);
  const launches = [0, 6, 12];
  const gpu = [{ s: 4, w: 30 }, { s: 34, w: 30 }, { s: 64, w: 30 }];
  const measured = synced ? 94 : 18;
  return (
    <div className="space-y-4">
      <Panel>
        <PanelHead
          title="CUDA is asynchronous"
          sub="CPU enqueues kernels and returns immediately; the GPU executes later"
          right={
            <button onClick={() => setSynced((v) => !v)} className={clsx("btn text-2xs", synced && "btn-accent")}>
              torch.cuda.synchronize(): {synced ? "on" : "off"}
            </button>
          }
        />
        <div className="space-y-3 p-4">
          <Lane label="CPU thread" hint="python dispatch">
            {launches.map((s, i) => (
              <Block key={i} start={s} width={4} color="#58a6ff" label={`launch k${i}`} />
            ))}
            {synced && <Block start={92} width={4} color="#d29922" label="sync" />}
          </Lane>
          <Lane label="CUDA stream" hint="kernel queue">
            {gpu.map((g, i) => (
              <Block key={i} start={g.s} width={g.w} color="#ee4c2c33" border label={`queued k${i}`} />
            ))}
          </Lane>
          <Lane label="GPU execution" hint="serial on stream">
            {gpu.map((g, i) => (
              <Block key={i} start={g.s} width={g.w} color="#ee4c2c" label={`exec k${i}`} />
            ))}
          </Lane>
          <div className="relative h-6">
            <div className="absolute left-0 top-2 h-px w-full bg-line" />
            <motion.div className="absolute top-0 flex flex-col items-center" animate={{ left: `${measured}%` }} transition={{ type: "spring", stiffness: 120, damping: 18 }}>
              <div className="h-4 w-px bg-ok" />
              <span className="mono whitespace-nowrap text-2xs text-ok">t = {measured} (measured)</span>
            </motion.div>
          </div>
        </div>
      </Panel>
      <Panel>
        <PanelHead title="Why your benchmark lies without synchronize()" />
        <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2">
          <CodeBlock>{`# WRONG — stops the clock at kernel launch, not execution
t0 = time.time()
logits = model(x)          # async: returns immediately
dt = time.time() - t0      # ~0.2ms (!) — measures dispatch only`}</CodeBlock>
          <CodeBlock>{`# RIGHT — wait for the GPU to actually finish
t0 = time.time()
logits = model(x)
torch.cuda.synchronize()   # block until the stream drains
dt = time.time() - t0      # real forward-pass time`}</CodeBlock>
        </div>
        <p className="px-4 pb-4 text-2xs leading-relaxed text-fg-faint">
          Toggle synchronize above: without it the "measured" marker stops at the last <em>launch</em> (~18), wildly
          under-reporting; with it, the marker waits for GPU completion (~94).
        </p>
      </Panel>
    </div>
  );
}

function Lane({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-28 shrink-0 text-right">
        <div className="text-2xs font-medium text-fg-muted">{label}</div>
        <div className="text-[9px] text-fg-faint">{hint}</div>
      </div>
      <div className="relative h-7 flex-1 rounded-md border border-line bg-ink-900">{children}</div>
    </div>
  );
}

function Block({ start, width, color, label, border }: { start: number; width: number; color: string; label: string; border?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="absolute top-1 flex h-5 items-center justify-center rounded text-[8px] font-medium text-fg"
      style={{ left: `${start}%`, width: `${width}%`, background: color, border: border ? "1px dashed #ee4c2c66" : "none" }}
      title={label}
    >
      <span className="truncate px-0.5">{label}</span>
    </motion.div>
  );
}
