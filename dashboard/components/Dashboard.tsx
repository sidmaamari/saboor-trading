"use client";

import { useEffect, useState, useCallback } from "react";
import StatCard from "./StatCard";
import PerformanceChart from "./PerformanceChart";

interface LivePosition {
  ticker: string;
  shares: number;
  entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  allocation_pct: number;
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
  livePositions: LivePosition[];
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

  const { benchmark, portfolio, livePositions } = data;
  const latest = benchmark[benchmark.length - 1];

  const totalValue = portfolio?.total_value ?? 100_000;
  const dailyPl = portfolio?.daily_pl ?? 0;
  const cumSaboor = latest?.cumulative_portfolio ?? 0;
  const cumSpy = latest?.cumulative_spy ?? 0;
  const alpha = cumSaboor - cumSpy;
  const hasTraded = livePositions.length > 0;

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
          value={cumSaboor === 0 ? "0.00%" : `${cumSaboor >= 0 ? "+" : ""}${cumSaboor.toFixed(2)}%`}
          color={cumSaboor > 0 ? "green" : cumSaboor < 0 ? "red" : "white"}
          sub={benchmark.length === 0 ? "No trades yet" : undefined}
        />
        <StatCard
          label="Alpha vs SPY"
          value={benchmark.length === 0 ? "—" : `${alpha >= 0 ? "+" : ""}${alpha.toFixed(2)}%`}
          sub={`SPY: ${cumSpy >= 0 ? "+" : ""}${cumSpy.toFixed(2)}%`}
          color={alpha > 0 ? "green" : alpha < 0 ? "red" : "white"}
        />
        <StatCard
          label="Daily P&L"
          value={dailyPl === 0 ? "$0" : `${dailyPl >= 0 ? "+$" : "-$"}${Math.abs(dailyPl).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          sub={`${livePositions.length} open position${livePositions.length !== 1 ? "s" : ""}`}
          color={dailyPl > 0 ? "green" : dailyPl < 0 ? "red" : "white"}
        />
      </div>

      {/* Chart */}
      <div className="bg-[#111] border border-[#222] rounded-xl p-6 mb-6">
        <h2 className="text-sm font-medium text-gray-400 mb-6">
          Cumulative Return — Saboor vs S&P 500
        </h2>
        <PerformanceChart data={benchmark} />
      </div>

      {/* Portfolio Breakdown */}
      <div className="bg-[#111] border border-[#222] rounded-xl p-6">
        <h2 className="text-sm font-medium text-gray-400 mb-4">Portfolio</h2>

        {/* Cash row always visible */}
        <div className="flex items-center justify-between py-3 border-b border-[#1a1a1a]">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-gray-600" />
            <span className="text-sm font-medium">Cash</span>
          </div>
          <div className="flex items-center gap-8">
            <span className="text-sm text-gray-400 w-20 text-right">
              ${(portfolio?.cash ?? totalValue).toLocaleString("en-US", { maximumFractionDigits: 0 })}
            </span>
            <span className="text-sm text-gray-500 w-14 text-right">
              {(((portfolio?.cash ?? totalValue) / totalValue) * 100).toFixed(1)}%
            </span>
          </div>
        </div>

        {!hasTraded ? (
          <p className="text-xs text-gray-600 text-center py-6">
            No open positions — first trades execute at market open.
          </p>
        ) : (
          livePositions.map((pos) => {
            const isCore = pos.unrealized_plpc !== undefined;
            return (
              <div
                key={pos.ticker}
                className="flex items-center justify-between py-3 border-b border-[#1a1a1a] last:border-0"
              >
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <div>
                    <span className="text-sm font-medium">{pos.ticker}</span>
                    <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-[#1a1a1a] text-gray-500">
                      {pos.shares} shares
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-8">
                  <span className="text-sm text-gray-400 w-24 text-right">
                    ${pos.market_value.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                  </span>
                  <span
                    className={`text-sm w-20 text-right font-medium ${
                      pos.unrealized_plpc >= 0 ? "text-green-400" : "text-red-400"
                    }`}
                  >
                    {pos.unrealized_plpc >= 0 ? "+" : ""}
                    {pos.unrealized_plpc.toFixed(2)}%
                  </span>
                  <span className="text-sm text-gray-500 w-14 text-right">
                    {pos.allocation_pct.toFixed(1)}%
                  </span>
                </div>
              </div>
            );
          })
        )}

        {/* Total row */}
        {hasTraded && (
          <div className="flex items-center justify-between pt-4 mt-1">
            <span className="text-xs text-gray-600 uppercase tracking-widest">Total</span>
            <div className="flex items-center gap-8">
              <span className="text-sm font-medium w-24 text-right">
                ${totalValue.toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </span>
              <span
                className={`text-sm font-medium w-20 text-right ${
                  dailyPl >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {dailyPl >= 0 ? "+$" : "-$"}
                {Math.abs(dailyPl).toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </span>
              <span className="text-sm text-gray-500 w-14 text-right">100%</span>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
