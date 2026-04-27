"use client";

import { useEffect, useState, useCallback } from "react";
import StatCard from "./StatCard";
import PerformanceChart from "./PerformanceChart";

interface Position {
  id: number;
  ticker: string;
  bucket: string;
  shares: number;
  entry_price: number;
  days_held: number;
}

interface BenchmarkRow {
  date: string;
  cumulative_portfolio: number;
  cumulative_spy: number;
}

interface Portfolio {
  cash: number;
  total_value: number;
  daily_pl: number;
}

interface DashboardData {
  benchmark: BenchmarkRow[];
  portfolio: Portfolio | null;
  openPositions: Position[];
}

export default function Dashboard({ initial }: { initial: DashboardData }) {
  const [data, setData] = useState(initial);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/data");
      const json = await res.json();
      setData(json);
      setLastUpdated(new Date());
    } catch {}
  }, []);

  useEffect(() => {
    const id = setInterval(refresh, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [refresh]);

  const { benchmark, portfolio, openPositions } = data;
  const latest = benchmark[benchmark.length - 1];

  const totalValue = portfolio?.total_value ?? 100_000;
  const dailyPl = portfolio?.daily_pl ?? 0;
  const cumSaboor = latest?.cumulative_portfolio ?? 0;
  const cumSpy = latest?.cumulative_spy ?? 0;
  const alpha = cumSaboor - cumSpy;

  return (
    <main className="max-w-5xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Saboor</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Autonomous Halal Trading — Paper Portfolio
          </p>
        </div>
        <p className="text-xs text-gray-600">
          Refreshes every 5 min · last at{" "}
          {lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="Portfolio Value"
          value={`$${totalValue.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          sub="Paper account"
        />
        <StatCard
          label="Total Return"
          value={`${cumSaboor >= 0 ? "+" : ""}${cumSaboor.toFixed(2)}%`}
          color={cumSaboor >= 0 ? "green" : "red"}
        />
        <StatCard
          label="Alpha vs SPY"
          value={`${alpha >= 0 ? "+" : ""}${alpha.toFixed(2)}%`}
          sub={`SPY: ${cumSpy >= 0 ? "+" : ""}${cumSpy.toFixed(2)}%`}
          color={alpha >= 0 ? "green" : "red"}
        />
        <StatCard
          label="Daily P&L"
          value={`${dailyPl >= 0 ? "+$" : "-$"}${Math.abs(dailyPl).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          sub={`${openPositions.length} open position${openPositions.length !== 1 ? "s" : ""}`}
          color={dailyPl >= 0 ? "green" : "red"}
        />
      </div>

      {/* Chart */}
      <div className="bg-[#111] border border-[#222] rounded-xl p-6 mb-6">
        <h2 className="text-sm font-medium text-gray-400 mb-6">
          Cumulative Return — Saboor vs S&P 500
        </h2>
        <PerformanceChart data={benchmark} />
      </div>

      {/* Open Positions */}
      {openPositions.length > 0 && (
        <div className="bg-[#111] border border-[#222] rounded-xl p-6">
          <h2 className="text-sm font-medium text-gray-400 mb-4">
            Open Positions
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-600 uppercase border-b border-[#1f1f1f]">
                <th className="text-left pb-2 font-medium">Ticker</th>
                <th className="text-left pb-2 font-medium">Bucket</th>
                <th className="text-right pb-2 font-medium">Shares</th>
                <th className="text-right pb-2 font-medium">Entry</th>
                <th className="text-right pb-2 font-medium">Days</th>
              </tr>
            </thead>
            <tbody>
              {openPositions.map((pos) => (
                <tr
                  key={pos.id}
                  className="border-b border-[#1a1a1a] last:border-0"
                >
                  <td className="py-2.5 font-medium">{pos.ticker}</td>
                  <td className="py-2.5">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${
                        pos.bucket === "core"
                          ? "bg-blue-500/10 text-blue-400"
                          : "bg-orange-500/10 text-orange-400"
                      }`}
                    >
                      {pos.bucket}
                    </span>
                  </td>
                  <td className="py-2.5 text-right text-gray-400">
                    {pos.shares}
                  </td>
                  <td className="py-2.5 text-right text-gray-400">
                    ${pos.entry_price?.toFixed(2)}
                  </td>
                  <td className="py-2.5 text-right text-gray-400">
                    {pos.days_held ?? 0}d
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
