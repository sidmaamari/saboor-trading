"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

interface BenchmarkRow {
  date: string;
  cumulative_portfolio: number;
  cumulative_spy: number;
}

export default function PerformanceChart({ data }: { data: BenchmarkRow[] }) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-600 text-sm">
        No trading data yet — chart populates after the first EOD run.
      </div>
    );
  }

  // Always start both lines from 0%
  const chartData = [
    { date: "Start", Saboor: 0, "S&P 500": 0 },
    ...data.map((d) => ({
      date: new Date(d.date).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      }),
      Saboor: parseFloat(d.cumulative_portfolio.toFixed(2)),
      "S&P 500": parseFloat(d.cumulative_spy.toFixed(2)),
    })),
  ];

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
        <XAxis
          dataKey="date"
          tick={{ fill: "#4b5563", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#4b5563", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v >= 0 ? "+" : ""}${v}%`}
        />
        <ReferenceLine y={0} stroke="#2a2a2a" />
        <Tooltip
          contentStyle={{
            backgroundColor: "#111",
            border: "1px solid #222",
            borderRadius: 8,
            fontSize: 12,
          }}
          labelStyle={{ color: "#9ca3af", marginBottom: 4 }}
          formatter={(v: number, name: string) => [
            `${v >= 0 ? "+" : ""}${v}%`,
            name,
          ]}
        />
        <Legend wrapperStyle={{ paddingTop: 16, fontSize: 12, color: "#6b7280" }} />
        <Line
          type="monotone"
          dataKey="Saboor"
          stroke="#22c55e"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#22c55e", strokeWidth: 0 }}
        />
        <Line
          type="monotone"
          dataKey="S&P 500"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#3b82f6", strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
