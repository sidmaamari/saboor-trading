"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

export const POSITION_COLORS = [
  "#22c55e",
  "#3b82f6",
  "#f59e0b",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#f97316",
  "#84cc16",
  "#e11d48",
  "#a78bfa",
  "#34d399",
  "#60a5fa",
];
export const CASH_COLOR = "#374151";

export interface PieSlice {
  name: string;
  value: number;
  pct: number;
  color: string;
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: PieSlice }> }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-[#0a0a0a] border border-[#2a2a2a] rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="font-semibold text-white mb-1">{d.name}</p>
      <p className="text-gray-400">${d.value.toLocaleString("en-US", { maximumFractionDigits: 0 })}</p>
      <p className="text-gray-500">{d.pct.toFixed(1)}% of portfolio</p>
    </div>
  );
};

export default function PortfolioPieChart({ slices }: { slices: PieSlice[] }) {
  return (
    <div className="flex flex-col sm:flex-row items-center gap-8">
      <div style={{ width: 190, height: 190, flexShrink: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              cx="50%"
              cy="50%"
              innerRadius={56}
              outerRadius={86}
              dataKey="value"
              paddingAngle={slices.length > 1 ? 2 : 0}
              strokeWidth={0}
            >
              {slices.map((s) => (
                <Cell key={s.name} fill={s.color} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-col gap-2.5 flex-1 w-full min-w-0">
        {slices.map((s) => (
          <div key={s.name} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: s.color }} />
              <span className="text-sm font-medium truncate">{s.name}</span>
            </div>
            <div className="flex items-center gap-5 flex-shrink-0">
              <span className="text-sm text-gray-400 tabular-nums">
                ${s.value.toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </span>
              <span className="text-sm text-gray-500 tabular-nums w-12 text-right">
                {s.pct.toFixed(1)}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
