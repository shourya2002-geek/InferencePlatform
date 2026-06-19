import clsx from "clsx";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { clamp } from "@/lib/format";

/* ----------------------------------------------------------------- Panel -- */
export function Panel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={clsx("panel", className)}>{children}</div>;
}

export function PanelHead({
  title,
  sub,
  right,
}: {
  title: React.ReactNode;
  sub?: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <div className="panel-head">
      <div className="min-w-0">
        <div className="text-[13px] font-semibold text-fg">{title}</div>
        {sub && <div className="text-2xs text-fg-faint">{sub}</div>}
      </div>
      {right}
    </div>
  );
}

/* ------------------------------------------------------------ PageHeader -- */
export function PageHeader({
  title,
  desc,
  source,
  right,
}: {
  title: string;
  desc: string;
  source?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line bg-ink-850/60 px-6 py-4">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold tracking-tight text-fg">{title}</h1>
        <p className="mt-0.5 max-w-3xl text-[13px] leading-relaxed text-fg-muted">{desc}</p>
        {source && (
          <div className="mt-1.5 inline-flex items-center gap-1.5 rounded border border-line bg-ink-800 px-1.5 py-0.5 text-2xs text-fg-faint">
            <span className="h-1.5 w-1.5 rounded-full bg-ok/70" />
            grounded in <span className="mono text-fg-muted">{source}</span>
          </div>
        )}
      </div>
      {right}
    </div>
  );
}

/* ------------------------------------------------------------- MetricCard -- */
export function MetricCard({
  label,
  value,
  unit,
  series,
  tone = "default",
  hint,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  series?: number[];
  tone?: "default" | "ok" | "warn" | "danger" | "torch" | "info" | "violet";
  hint?: string;
}) {
  const toneColor = {
    default: "#58a6ff",
    ok: "#3fb950",
    warn: "#d29922",
    danger: "#f85149",
    torch: "#ee4c2c",
    info: "#58a6ff",
    violet: "#a371f7",
  }[tone];
  const data = (series ?? []).map((v, i) => ({ i, v }));
  const gradId = `grad-${label.replace(/[^a-zA-Z0-9]/g, "")}`;
  return (
    <div className="panel relative overflow-hidden p-3">
      <div className="flex items-center justify-between">
        <span className="text-2xs font-medium uppercase tracking-wider text-fg-faint">{label}</span>
        {hint && <span className="text-2xs text-fg-faint">{hint}</span>}
      </div>
      <div className="mt-1.5 flex items-end gap-1">
        <span className="kpi text-2xl font-semibold text-fg">{value}</span>
        {unit && <span className="mb-0.5 text-xs text-fg-faint">{unit}</span>}
      </div>
      {data.length > 1 && (
        <div className="mt-2 h-8 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 2, bottom: 0, left: 0, right: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={toneColor} stopOpacity={0.45} />
                  <stop offset="100%" stopColor={toneColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke={toneColor}
                strokeWidth={1.5}
                fill={`url(#${gradId})`}
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------- Bar -- */
export function Bar({
  value,
  tone = "torch",
  className,
}: {
  value: number; // 0..1
  tone?: "torch" | "ok" | "warn" | "danger" | "info";
  className?: string;
}) {
  const color = {
    torch: "bg-torch",
    ok: "bg-ok",
    warn: "bg-warn",
    danger: "bg-danger",
    info: "bg-info",
  }[tone];
  return (
    <div className={clsx("h-1.5 w-full overflow-hidden rounded-full bg-ink-600", className)}>
      <div
        className={clsx("h-full rounded-full transition-all duration-300", color)}
        style={{ width: `${clamp(value, 0, 1) * 100}%` }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ Badge -- */
export function Badge({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "ok" | "warn" | "danger" | "info" | "torch" | "violet";
}) {
  const cls = {
    default: "border-line bg-ink-750 text-fg-muted",
    ok: "border-ok/30 bg-ok/10 text-ok",
    warn: "border-warn/30 bg-warn/10 text-warn",
    danger: "border-danger/30 bg-danger/10 text-danger",
    info: "border-info/30 bg-info/10 text-info",
    torch: "border-torch/30 bg-torch/10 text-torch-soft",
    violet: "border-violet/30 bg-violet/10 text-violet",
  }[tone];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-2xs font-medium",
        cls,
      )}
    >
      {children}
    </span>
  );
}

/* -------------------------------------------------------------- CodeBlock -- */
export function CodeBlock({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <pre
      className={clsx(
        "overflow-x-auto rounded-md border border-line bg-ink-900 p-3 text-xs leading-relaxed text-fg-muted",
        className,
      )}
    >
      <code className="mono">{children}</code>
    </pre>
  );
}

/* ------------------------------------------------------------------- Stat -- */
export function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "ok" | "warn" | "danger" | "torch";
}) {
  const color = tone
    ? { ok: "text-ok", warn: "text-warn", danger: "text-danger", torch: "text-torch-soft" }[tone]
    : "text-fg";
  return (
    <div className="flex flex-col">
      <span className="text-2xs uppercase tracking-wider text-fg-faint">{label}</span>
      <span className={clsx("kpi text-base font-semibold", color)}>{value}</span>
    </div>
  );
}

/* ----------------------------------------------------------------- Legend -- */
export function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-2xs text-fg-muted">
      <span className="h-2 w-2 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  );
}
