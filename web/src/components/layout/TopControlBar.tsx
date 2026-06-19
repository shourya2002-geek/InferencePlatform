import clsx from "clsx";
import { Pause, Play, RotateCcw } from "lucide-react";
import { useSim } from "@/state/SimulationContext";
import { SCENARIOS } from "@/sim/scenarios";
import { RUNTIMES, BATCH_PRESETS, WORKER_PRESETS } from "@/sim/constants";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-2xs font-medium uppercase tracking-wider text-fg-faint">{label}</span>
      {children}
    </label>
  );
}

const selectCls =
  "h-7 rounded-md border border-line bg-ink-750 px-2 text-xs font-medium text-fg outline-none focus:border-line-strong";

export function TopControlBar() {
  const { state, start, pause, reset, setControls, applyScenario } = useSim();
  const c = state.controls;

  return (
    <div className="flex items-center gap-4 border-b border-line bg-ink-850 px-4 py-2">
      <div className="flex items-center gap-1.5">
        {state.running ? (
          <button className="btn btn-accent" onClick={pause}>
            <Pause className="h-3.5 w-3.5" /> Pause
          </button>
        ) : (
          <button className="btn btn-accent" onClick={start}>
            <Play className="h-3.5 w-3.5" /> Start
          </button>
        )}
        <button className="btn" onClick={reset} title="Reset simulation">
          <RotateCcw className="h-3.5 w-3.5" /> Reset
        </button>
      </div>

      <div className="h-8 w-px bg-line" />

      <div className="flex items-end gap-3 overflow-x-auto">
        <Field label="Scenario">
          <select
            className={selectCls}
            defaultValue=""
            onChange={(e) => e.target.value && applyScenario(e.target.value)}
          >
            <option value="" disabled>
              select…
            </option>
            {SCENARIOS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label={`Traffic · ${c.rps} RPS`}>
          <input
            type="range"
            min={10}
            max={5000}
            step={10}
            value={c.rps}
            onChange={(e) => setControls({ rps: Number(e.target.value) })}
            className="h-7 w-32 accent-torch"
          />
        </Field>

        <Field label="Runtime">
          <select
            className={selectCls}
            value={c.runtime}
            onChange={(e) => setControls({ runtime: e.target.value })}
          >
            {RUNTIMES.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Workers">
          <div className="flex gap-1">
            {WORKER_PRESETS.map((w) => (
              <button
                key={w}
                onClick={() => setControls({ workers: w })}
                className={clsx(
                  "h-7 w-7 rounded-md border text-xs font-semibold mono",
                  c.workers === w
                    ? "border-torch/50 bg-torch/15 text-torch-soft"
                    : "border-line bg-ink-750 text-fg-muted hover:text-fg",
                )}
              >
                {w}
              </button>
            ))}
          </div>
        </Field>

        <Field label="Batch">
          <select
            className={selectCls}
            value={c.maxBatchSize}
            onChange={(e) => setControls({ maxBatchSize: Number(e.target.value) })}
          >
            {BATCH_PRESETS.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </Field>

        <Field label={`Speed · ${c.speed}×`}>
          <input
            type="range"
            min={0.25}
            max={4}
            step={0.25}
            value={c.speed}
            onChange={(e) => setControls({ speed: Number(e.target.value) })}
            className="h-7 w-24 accent-torch"
          />
        </Field>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={() => setControls({ batchingEnabled: !c.batchingEnabled })}
          className={clsx(
            "btn text-xs",
            c.batchingEnabled ? "btn-accent" : "",
          )}
          title="Toggle dynamic batching"
        >
          batching: {c.batchingEnabled ? "on" : "off"}
        </button>
      </div>
    </div>
  );
}
