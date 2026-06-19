import { NavLink } from "react-router-dom";
import clsx from "clsx";
import { Flame } from "lucide-react";
import { NAV } from "./nav";
import { useSim } from "@/state/SimulationContext";

const GROUP_ORDER = ["Platform", "Simulate", "PyTorch", "Reliability", "Operate"];

export function Sidebar() {
  const { state } = useSim();
  const grouped = GROUP_ORDER.map((g) => ({ g, items: NAV.filter((n) => n.group === g) }));

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-line bg-ink-850">
      <div className="flex items-center gap-2.5 border-b border-line px-4 py-3.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-torch/15 ring-1 ring-torch/30">
          <Flame className="h-4 w-4 text-torch" strokeWidth={2.2} />
        </div>
        <div className="leading-tight">
          <div className="text-[13px] font-semibold tracking-tight text-fg">
            Inference Platform
          </div>
          <div className="text-2xs font-medium text-fg-faint">systems simulator</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2.5 py-3">
        {grouped.map(({ g, items }) => (
          <div key={g} className="mb-4">
            <div className="px-2 pb-1.5 text-2xs font-semibold uppercase tracking-wider text-fg-faint">
              {g}
            </div>
            <div className="space-y-0.5">
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    clsx(
                      "group flex items-center gap-2.5 rounded-md px-2 py-1.5 text-[13px] font-medium transition-colors",
                      isActive
                        ? "bg-ink-700 text-fg"
                        : "text-fg-muted hover:bg-ink-800 hover:text-fg",
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <item.icon
                        className={clsx(
                          "h-4 w-4 shrink-0",
                          isActive ? "text-torch" : "text-fg-faint group-hover:text-fg-muted",
                        )}
                        strokeWidth={2}
                      />
                      <span className="flex-1 truncate">{item.label}</span>
                      {item.hint && (
                        <span
                          className={clsx(
                            "rounded px-1 py-px text-[9px] font-semibold uppercase tracking-wide",
                            item.hint === "flagship"
                              ? "bg-torch/15 text-torch-soft"
                              : "text-fg-faint",
                          )}
                        >
                          {item.hint}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-line px-3 py-3">
        <div className="flex items-center justify-between text-2xs text-fg-faint">
          <span className="mono">t={state.tSec.toFixed(1)}s</span>
          <span className="flex items-center gap-1.5">
            <span
              className={clsx(
                "h-1.5 w-1.5 rounded-full",
                state.running ? "bg-ok animate-pulse-line" : "bg-fg-faint",
              )}
            />
            {state.running ? "running" : "paused"}
          </span>
        </div>
      </div>
    </aside>
  );
}
