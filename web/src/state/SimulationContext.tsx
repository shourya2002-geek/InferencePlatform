import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  DEFAULT_CONTROLS,
  createInitialState,
  reconcileWorkers,
  stepState,
} from "@/sim/engine";
import type { FailureKind, SimControls, SimState } from "@/sim/types";
import { type Replay } from "@/sim/replays";
import { scenarioById } from "@/sim/scenarios";

const TICK_MS = 120; // wall-clock cadence
const SIM_DT_MS = 100; // sim time advanced per tick at speed=1

interface ReplayRun {
  replay: Replay;
  startedAt: number;
  appliedIdx: number;
}

interface SimAPI {
  state: SimState;
  start: () => void;
  pause: () => void;
  reset: () => void;
  setControls: (patch: Partial<SimControls>) => void;
  applyScenario: (id: string) => void;
  inject: (k: FailureKind) => void;
  clearFailure: (k: FailureKind) => void;
  clearAllFailures: () => void;
  runReplay: (r: Replay) => void;
  stopReplay: () => void;
  activeReplayId: string | null;
  replayProgress: number; // 0..1
}

const Ctx = createContext<SimAPI | null>(null);

export function SimulationProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SimState>(() => {
    const s = createInitialState(DEFAULT_CONTROLS);
    s.running = true; // live on load — it's a demo
    return s;
  });
  const stateRef = useRef(state);
  stateRef.current = state;

  const replayRef = useRef<ReplayRun | null>(null);
  const [activeReplayId, setActiveReplayId] = useState<string | null>(null);
  const [replayProgress, setReplayProgress] = useState(0);

  // The single simulation loop.
  useEffect(() => {
    const handle = window.setInterval(() => {
      const cur = stateRef.current;
      if (!cur.running) return;
      const dt = SIM_DT_MS * cur.controls.speed;

      // Drive replay keyframes by sim time.
      const run = replayRef.current;
      let pending: Partial<SimState> | null = null;
      if (run) {
        const elapsed = cur.tSec - run.startedAt;
        const kfs = run.replay.keyframes;
        while (run.appliedIdx < kfs.length && kfs[run.appliedIdx].atSec <= elapsed) {
          const kf = kfs[run.appliedIdx];
          pending = applyKeyframe(cur, kf, pending);
          run.appliedIdx += 1;
        }
        setReplayProgress(Math.min(1, elapsed / run.replay.durationSec));
        if (elapsed >= run.replay.durationSec) {
          replayRef.current = null;
          setActiveReplayId(null);
        }
      }

      setState((s) => {
        let base = s;
        if (pending) {
          base = { ...s, ...pending };
          if (pending.controls && pending.controls.workers !== s.controls.workers) {
            base = { ...base, workers: base.workers.slice() };
            reconcileWorkers(base);
          }
        }
        return stepState(base, dt);
      });
    }, TICK_MS);
    return () => window.clearInterval(handle);
  }, []);

  const start = useCallback(() => setState((s) => ({ ...s, running: true })), []);
  const pause = useCallback(() => setState((s) => ({ ...s, running: false })), []);

  const reset = useCallback(() => {
    replayRef.current = null;
    setActiveReplayId(null);
    setReplayProgress(0);
    setState((s) => {
      const fresh = createInitialState(s.controls);
      fresh.running = s.running;
      return fresh;
    });
  }, []);

  const setControls = useCallback((patch: Partial<SimControls>) => {
    setState((s) => {
      const next = { ...s, controls: { ...s.controls, ...patch } };
      if (patch.workers !== undefined) reconcileWorkers(next);
      return next;
    });
  }, []);

  const applyScenario = useCallback((id: string) => {
    const sc = scenarioById(id);
    if (!sc) return;
    replayRef.current = null;
    setActiveReplayId(null);
    setState((s) => {
      const next = createInitialState({ ...s.controls, ...sc.controls });
      next.running = true;
      next.activeFailures = new Set(sc.failures ?? []);
      reconcileWorkers(next);
      return next;
    });
  }, []);

  const inject = useCallback((k: FailureKind) => {
    setState((s) => {
      const f = new Set(s.activeFailures);
      f.add(k);
      return { ...s, activeFailures: f, running: true };
    });
  }, []);

  const clearFailure = useCallback((k: FailureKind) => {
    setState((s) => {
      const f = new Set(s.activeFailures);
      f.delete(k);
      return { ...s, activeFailures: f };
    });
  }, []);

  const clearAllFailures = useCallback(() => {
    setState((s) => ({ ...s, activeFailures: new Set() }));
  }, []);

  const runReplay = useCallback((r: Replay) => {
    setState((s) => {
      const next = createInitialState({ ...s.controls, ...r.base });
      next.running = true;
      reconcileWorkers(next);
      replayRef.current = { replay: r, startedAt: next.tSec, appliedIdx: 0 };
      setActiveReplayId(r.id);
      setReplayProgress(0);
      return next;
    });
  }, []);

  const stopReplay = useCallback(() => {
    replayRef.current = null;
    setActiveReplayId(null);
    setReplayProgress(0);
  }, []);

  const api = useMemo<SimAPI>(
    () => ({
      state,
      start,
      pause,
      reset,
      setControls,
      applyScenario,
      inject,
      clearFailure,
      clearAllFailures,
      runReplay,
      stopReplay,
      activeReplayId,
      replayProgress,
    }),
    [state, start, pause, reset, setControls, applyScenario, inject, clearFailure, clearAllFailures, runReplay, stopReplay, activeReplayId, replayProgress],
  );

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

function applyKeyframe(
  cur: SimState,
  kf: { controls?: Partial<SimControls>; inject?: FailureKind; clear?: FailureKind },
  pending: Partial<SimState> | null,
): Partial<SimState> {
  const p: Partial<SimState> = pending ?? {};
  if (kf.controls) {
    p.controls = { ...(p.controls ?? cur.controls), ...kf.controls };
  }
  if (kf.inject || kf.clear) {
    const f = new Set(p.activeFailures ?? cur.activeFailures);
    if (kf.inject) f.add(kf.inject);
    if (kf.clear) f.delete(kf.clear);
    p.activeFailures = f;
  }
  return p;
}

export function useSim(): SimAPI {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSim must be used within SimulationProvider");
  return ctx;
}
