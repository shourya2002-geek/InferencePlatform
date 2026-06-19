import { useState } from "react";
import clsx from "clsx";
import { motion } from "framer-motion";
import { ArrowUpCircle, Check, RotateCcw, Undo2 } from "lucide-react";
import { Badge, Bar, CodeBlock, Panel, PanelHead, PageHeader, Stat } from "@/components/primitives";
import { REGISTRY_MODELS } from "@/sim/content";
import { fmtMs } from "@/lib/format";

type Phase = "idle" | "warming" | "cutover";

export default function ModelRegistry() {
  const [latest, setLatest] = useState("v2");
  const [traffic, setTraffic] = useState<Record<string, number>>({ v1: 0, v2: 100, v3: 0 });
  const [phase, setPhase] = useState<Phase>("idle");
  const [target, setTarget] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);

  const addLog = (m: string) => setLog((l) => [`${m}`, ...l].slice(0, 8));

  const promote = (v: string) => {
    if (v === latest) return;
    setTarget(v);
    setPhase("warming");
    addLog(`POST /v1/models/resnet/promote?version=${v} — warming ${v}…`);
    setTimeout(() => {
      setPhase("cutover");
      addLog(`${v} warm — flipping 'latest' (zero-downtime cutover)`);
      setTraffic({ v1: 0, v2: 0, v3: 0, [v]: 100 });
      setLatest(v);
      setTimeout(() => {
        setPhase("idle");
        setTarget(null);
        addLog(`promotion complete — resnet:${v} now serving 100%`);
      }, 900);
    }, 1100);
  };

  const canary = (v: string, pct: number) => {
    const other = latest;
    if (v === other) return;
    setTraffic({ v1: 0, v2: 0, v3: 0, [other]: 100 - pct, [v]: pct });
  };

  return (
    <div>
      <PageHeader
        title="Model Registry"
        desc="resnet v1/v2/v3 with versioning, canary traffic splits, promotion, rollback and zero-downtime hot reload. The registry warm-loads a version before flipping 'latest', so the first post-promotion request never eats a cold start."
        source="inference_worker/domain/registry.py · catalog.py"
      />

      <div className="space-y-4 p-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {REGISTRY_MODELS.map((m) => {
            const isLatest = m.version === latest;
            const isWarming = phase === "warming" && target === m.version;
            const t = traffic[m.version] ?? 0;
            return (
              <motion.div key={m.version} layout>
                <Panel className={clsx(isLatest && "ring-1 ring-torch/40")}>
                  <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
                    <span className="flex items-center gap-2">
                      <span className="mono text-sm font-semibold text-fg">resnet:{m.version}</span>
                      {isLatest && <Badge tone="torch">latest</Badge>}
                      {isWarming && <Badge tone="warn">warming…</Badge>}
                    </span>
                    <Badge tone={m.state === "stable" ? "ok" : m.state === "canary" ? "violet" : "default"}>{m.state}</Badge>
                  </div>
                  <div className="space-y-3 p-4">
                    <div className="grid grid-cols-3 gap-2">
                      <Stat label="Params" value={m.params} />
                      <Stat label="Capacity" value={m.capacity} />
                      <Stat label="batch=1" value={fmtMs(m.baselineMs)} tone="warn" />
                    </div>
                    <div>
                      <div className="mb-1 flex justify-between text-2xs text-fg-faint">
                        <span>traffic</span>
                        <span className="mono">{t}%</span>
                      </div>
                      <Bar value={t / 100} tone={isLatest ? "torch" : "info"} />
                    </div>
                    <div className="flex gap-1.5">
                      <button className="btn flex-1 text-2xs" disabled={isLatest || phase !== "idle"} onClick={() => promote(m.version)}>
                        <ArrowUpCircle className="h-3 w-3" /> Promote
                      </button>
                      <button className="btn text-2xs" disabled={isLatest || phase !== "idle"} onClick={() => canary(m.version, 10)} title="send 10% canary traffic">
                        10% canary
                      </button>
                    </div>
                  </div>
                </Panel>
              </motion.div>
            );
          })}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Panel className="lg:col-span-2">
            <PanelHead
              title="Zero-downtime promotion"
              sub="warm → cutover → done"
              right={
                <button className="btn text-2xs" disabled={phase !== "idle"} onClick={() => promote(latest === "v2" ? "v3" : "v2")}>
                  <RotateCcw className="h-3 w-3" /> Demo promote
                </button>
              }
            />
            <div className="p-4">
              <div className="flex items-center gap-2">
                {(["idle", "warming", "cutover"] as Phase[]).map((p, i) => (
                  <div key={p} className="flex flex-1 items-center gap-2">
                    <div
                      className={clsx(
                        "flex-1 rounded-md border px-3 py-2.5 text-center text-xs font-medium",
                        phase === p && p !== "idle"
                          ? "border-torch/50 bg-torch/15 text-torch-soft"
                          : "border-line bg-ink-900 text-fg-faint",
                      )}
                    >
                      {p === "idle" ? "1 · request promote" : p === "warming" ? "2 · warm-load new version" : "3 · flip 'latest'"}
                    </div>
                    {i < 2 && <span className="text-fg-faint">→</span>}
                  </div>
                ))}
              </div>
              <CodeBlock className="mt-4">{`# registry.promote(): warm BEFORE flipping latest → no cold start
async def promote(self, name, version):
    await self.preload(name, version)   # load + warmup new version
    self._catalog.set_latest(name, version)   # atomic cutover

# operator / CI triggers it over HTTP:
curl -X POST "localhost:8090/v1/models/resnet/promote?version=${latest}"`}</CodeBlock>
              <div className="mt-3 flex gap-2">
                <button className="btn text-2xs" disabled={phase !== "idle"} onClick={() => { const prev = latest === "v3" ? "v2" : "v1"; promote(prev); }}>
                  <Undo2 className="h-3 w-3" /> Rollback to previous
                </button>
                <span className="self-center text-2xs text-fg-faint">
                  rollback is just a promote of the prior version — same safe path.
                </span>
              </div>
            </div>
          </Panel>

          <Panel>
            <PanelHead title="Registry log" />
            <div className="max-h-72 space-y-1.5 overflow-y-auto p-3">
              {log.length === 0 && <div className="px-1 py-4 text-center text-2xs text-fg-faint">Promote a version to see the cutover sequence.</div>}
              {log.map((l, i) => (
                <div key={i} className="flex items-start gap-2 text-2xs">
                  <Check className="mt-0.5 h-3 w-3 shrink-0 text-ok" />
                  <span className="mono text-fg-muted">{l}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
