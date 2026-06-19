import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface SeriesDef {
  key: string;
  color: string;
  label: string;
  kind?: "line" | "area";
  dashed?: boolean;
}

export function TimeSeries({
  data,
  series,
  height = 200,
  yUnit,
  yWidth = 38,
  domainMax,
}: {
  // recharts consumes loosely-typed row objects
  data: any[];
  series: SeriesDef[];
  height?: number;
  yUnit?: string;
  yWidth?: number;
  domainMax?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 10, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#1a212c" strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="t"
          tick={{ fontSize: 10, fill: "#677386" }}
          tickLine={false}
          axisLine={{ stroke: "#1e2733" }}
          minTickGap={40}
          tickFormatter={(v) => `${Math.round(v)}s`}
        />
        <YAxis
          width={yWidth}
          tick={{ fontSize: 10, fill: "#677386" }}
          tickLine={false}
          axisLine={false}
          domain={[0, domainMax ?? "auto"]}
          tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`)}
        />
        <Tooltip
          contentStyle={{ background: "#11151d", border: "1px solid #2b3544", borderRadius: 8 }}
          labelFormatter={(v) => `t = ${Number(v).toFixed(1)}s`}
          formatter={(val: number, name) => [
            `${typeof val === "number" ? val.toLocaleString() : val}${yUnit ?? ""}`,
            name,
          ]}
        />
        {series.map((s) =>
          s.kind === "area" ? (
            <Area
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              fill={s.color}
              fillOpacity={0.12}
              strokeWidth={1.6}
              isAnimationActive={false}
              dot={false}
            />
          ) : (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={1.8}
              strokeDasharray={s.dashed ? "4 3" : undefined}
              isAnimationActive={false}
              dot={false}
            />
          ),
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
