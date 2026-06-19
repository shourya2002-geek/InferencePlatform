import clsx from "clsx";
import { motion } from "framer-motion";
import { GraduationCap, Play, Square } from "lucide-react";
import { Badge, Bar, MetricCard, Panel, PanelHead, PageHeader } from "@/components/primitives";
import { FlowDiagram } from "@/components/viz/FlowDiagram";
import { useSim } from "@/state/SimulationContext";
import { REPLAYS, replayById } from "@/sim/replays";
import { fmtCompact, fmtMs, fmtPct } from "@/lib/format";

export default function ReplayCenter() {
  const { state, runReplay, stopReplay, activeReplayId, replayProgress } = useSim();
  const active = activeReplayId ? replayById(activeReplayId) : null;

  // current keyframe note for the active replay
  let curNote = "";
  if (active) {
    const elapsed = replayProgress * active.durationSec;
    const passed = active.keyframes.filter((k) => k.atSec <= elapsed);
    curNote = passed.length ? passed[passed.length - 1].note : active.keyframes[0]?.note ?? "";
  }

  return (
    <div>
      <PageHeader
        title="Replay Center"
        desc="Prebuilt, auto-animating scenarios for talks and demos. Each replay scripts the controls and failures over time and narrates what's happening — just hit play and present."
        source="sim/replays.ts"
      />

      <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-3">
        {/* replay list */}
        <div className="space-y-3 lg:col-span-1">
          {REPLAYS.map((r) => {
            const on = activeReplayId === r.id;
            return (
              <button
                key={r.id}
                onClick={() => (on ? stopReplay() : runReplay(r))}
                className={clsx(
                  "w-full rounded-lg border p-3 text-left transition-all",
                  on ? "border-torch/60 bg-torch/10 shadow-glow" : "border-line bg-ink-800 hover:border-line-strong",
                )}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-semibold text-fg">{r.name}</span>
                  {on ? (
                    <Square className="h-3.5 w-3.5 text-torch" />
                  ) : (
                    <Play className="h-3.5 w-3.5 text-fg-faint" />
                  )}
                </div>
                <p className="mt-1 text-2xs leading-relaxed text-fg-muted">{r.summary}</p>
                <div className="mt-2 flex items-center gap-1.5 text-2xs text-fg-faint">
                  <GraduationCap className="h-3 w-3" />
                  <span className="truncate">{r.teaches}</span>
                </div>
                {on && (
                  <div className="mt-2">
                    <Bar value={replayProgress} tone="torch" />
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* live stage */}
        <div className="space-y-4 lg:col-span-2">
          <Panel>
            <PanelHead
              title={active ? active.name : "Select a replay"}
              sub={active ? `${(replayProgress * active.durationSec).toFixed(0)}s / ${active.durationSec}s` : "auto-animated scenario"}
              right={
                active && (
                  <Badge tone="torch">
                    <motion.span animate={{ opacity: [1, 0.4, 1] }} transition={{ repeat: Infinity, duration: 1.4 }}>
                      ● live
                    </motion.span>
                  </Badge>
                )
              }
            />
            <div className="p-4">
              {active ? (
                <>
                  <div className="mb-4 rounded-md border border-line bg-ink-900 px-3 py-2.5">
                    <div className="text-2xs font-semibold uppercase tracking-wider text-fg-faint">now</div>
                    <motion.div key={curNote} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="mt-0.5 text-[13px] text-fg">
                      {curNote}
                    </motion.div>
                  </div>
                  <FlowDiagram />
                </>
              ) : (
                <div className="flex h-40 items-center justify-center text-sm text-fg-faint">
                  Pick a scenario on the left to start an automated walkthrough.
                </div>
              )}
            </div>
          </Panel>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <MetricCard label="Served" value={fmtCompact(state.achievedRps)} unit="rps" tone="torch" series={state.history.map((d) => d.rps).slice(-30)} />
            <MetricCard label="Queue" value={fmtCompact(state.queueDepth)} tone={state.queueDepth > 2000 ? "danger" : "default"} series={state.history.map((d) => d.queueDepth).slice(-30)} />
            <MetricCard label="p99" value={fmtMs(state.p99)} tone="warn" series={state.history.map((d) => d.p99).slice(-30)} />
            <MetricCard label="Errors" value={fmtPct(state.errorRate, 1)} tone={state.errorRate > 0.05 ? "danger" : "ok"} series={state.history.map((d) => d.errorRate).slice(-30)} />
          </div>
        </div>
      </div>
    </div>
  );
}
