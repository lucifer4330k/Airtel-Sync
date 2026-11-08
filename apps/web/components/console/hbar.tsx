"use client";

import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/**
 * Single-series horizontal bar chart. One hue (--chart), thin bars with a
 * 4px rounded data end, recessive grid, value labels at the bar end, hover
 * tooltip. Category names sit on the axis; numbers stay in ink, not color.
 */
export function HBar<T extends Record<string, unknown>>({
  data,
  category,
  value,
  format,
  tooltip,
  label,
}: {
  data: T[];
  category: keyof T & string;
  value: keyof T & string;
  format: (v: number) => string;
  tooltip?: (row: T) => string;
  label: string;
}) {
  const height = Math.max(160, data.length * 34 + 30);
  return (
    <figure aria-label={label} className="w-full">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 64, bottom: 4, left: 4 }} barCategoryGap={8}>
          <CartesianGrid horizontal={false} stroke="rgb(var(--line))" strokeDasharray="2 4" />
          <XAxis type="number" hide domain={[0, "dataMax"]} />
          <YAxis
            type="category"
            dataKey={category}
            width={170}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "rgb(var(--ink-soft))", fontSize: 13 }}
          />
          <Tooltip
            cursor={{ fill: "rgb(var(--line) / 0.4)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const row = payload[0].payload as T;
              return (
                <div className="rounded-bill border border-line bg-surface px-3 py-2 text-sm shadow-sm">
                  <p className="font-medium">{String(row[category])}</p>
                  <p className="money text-ink-soft">{tooltip ? tooltip(row) : format(Number(row[value]))}</p>
                </div>
              );
            }}
          />
          <Bar dataKey={value} fill="rgb(var(--chart))" radius={[0, 4, 4, 0]} maxBarSize={22} isAnimationActive={false}>
            <LabelList
              dataKey={value}
              position="right"
              formatter={(v: number) => format(v)}
              style={{ fill: "rgb(var(--ink))", fontSize: 12, fontVariantNumeric: "tabular-nums" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}
