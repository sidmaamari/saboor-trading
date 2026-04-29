"use client";

import { useEffect, useState, useCallback } from "react";
import StatCard from "./StatCard";
import PerformanceChart from "./PerformanceChart";
import PortfolioPieChart, { POSITION_COLORS, CASH_COLOR, type PieSlice } from "./PortfolioPieChart";

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
  const cashValue = portfolio?.cash ?? totalValue;
  const dailyPl = portfolio?.daily_pl ?? 0;
  const cumSaboor = latest?.cumulative_portfolio ?? 0;
  const cumSpy = latest?.cumulative_spy ?? 0;
  const alpha = cumSaboor - cumSpy;
  const hasPositions = livePositions.length > 0;

  const pieSlices: PieSlice[] = [
    ...livePositions.map((pos, i) => ({
      name: pos.ticker,
      value: pos.market_value,
      pct: pos.allocation_pct,
      color: POSITION_COLORS[i % POSITION_COLORS.length],
    })),
    {
      name: "Cash",
      value: cashValue,
      pct: totalValue > 0 ? (cashValue / totalValue) * 100 : 100,
      color: CASH_COLOR,
    },
  ];

  return (
    <main className="max-w-5xl mx-auto px-4 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Saboor</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Autonomous Halal Investing — Paper Portfolio
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

      {/* Performance Chart */}
      <div className="bg-[#111] border border-[#222] rounded-xl p-6 mb-6">
        <h2 className="text-sm font-medium text-gray-400 mb-6">
          Cumulative Return — Saboor vs S&amp;P 500
        </h2>
        <PerformanceChart data={benchmark} />
      </div>

      {/* Portfolio — Pie Chart + Position List */}
      <div className="bg-[#111] border border-[#222] rounded-xl p-6">
        <h2 className="text-sm font-medium text-gray-400 mb-6">Portfolio Allocation</h2>

        {/* Pie Chart */}
        <PortfolioPieChart slices={pieSlices} />

        {/* Divider */}
        <div className="border-t border-[#1a1a1a] mt-6 mb-4" />

        {/* Position List Header */}
        <div className="hidden sm:grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-x-4 px-1 mb-2">
          <span className="text-xs text-gray-600 uppercase tracking-widest">Position</span>
          <span className="text-xs text-gray-600 uppercase tracking-widest text-right">Shares</span>
          <span className="text-xs text-gray-600 uppercase tracking-widest text-right">Entry</span>
          <span className="text-xs text-gray-600 uppercase tracking-widest text-right">Price</span>
          <span className="text-xs text-gray-600 uppercase tracking-widest text-right">Value</span>
          <span className="text-xs text-gray-600 uppercase tracking-widest text-right">P&amp;L</span>
        </div>

        {/* Cash row */}
        <div className="flex items-center justify-between py-3 border-b border-[#1a1a1a]">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: CASH_COLOR }} />
            <span className="text-sm font-medium">Cash</span>
          </div>
          <div className="flex items-center gap-6 sm:gap-8">
            <span className="text-sm text-gray-400 tabular-nums">
              ${cashValue.toLocaleString("en-US", { maximumFractionDigits: 0 })}
            </span>
            <span className="text-sm text-gray-500 tabular-nums w-14 text-right">
              {((cashValue / totalValue) * 100).toFixed(1)}%
            </span>
          </div>
        </div>

        {!hasPositions ? (
          <p className="text-xs text-gray-600 text-center py-6">
            No open positions — first trades execute at market open.
          </p>
        ) : (
          livePositions.map((pos, i) => {
            const color = POSITION_COLORS[i % POSITION_COLORS.length];
            const plColor = pos.unrealized_plpc >= 0 ? "text-green-400" : "text-red-400";
            return (
              <div
                key={pos.ticker}
                className="py-3 border-b border-[#1a1a1a] last:border-0"
              >
                {/* Mobile layout */}
                <div className="flex items-center justify-between sm:hidden">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                    <div>
                      <span className="text-sm font-medium">{pos.ticker}</span>
                      <span className="ml-2 text-xs text-gray-600">{pos.shares} sh</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-400 tabular-nums">
                      ${pos.market_value.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                    <span className={`text-sm tabular-nums font-medium ${plColor}`}>
                      {pos.unrealized_plpc >= 0 ? "+" : ""}{pos.unrealized_plpc.toFixed(2)}%
                    </span>
                  </div>
                </div>

                {/* Desktop layout */}
                <div className="hidden sm:grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-x-4 items-center px-1">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
                    <span className="text-sm font-medium">{pos.ticker}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-[#1a1a1a] text-gray-500">
                      {pos.allocation_pct.toFixed(1)}%
                    </span>
                  </div>
                  <span className="text-sm text-gray-400 tabular-nums text-right">
                    {pos.shares.toLocaleString("en-US", { maximumFractionDigits: 4 })}
                  </span>
                  <span className="text-sm text-gray-500 tabular-nums text-right">
                    ${pos.entry_price.toFixed(2)}
                  </span>
                  <span className="text-sm text-gray-400 tabular-nums text-right">
                    ${pos.current_price.toFixed(2)}
                  </span>
                  <span className="text-sm text-gray-300 tabular-nums text-right font-medium">
                    ${pos.market_value.toLocaleString("en-US", { maximumFractionDigits: 0 })}
                  </span>
                  <div className="text-right">
                    <span className={`text-sm tabular-nums font-medium ${plColor}`}>
                      {pos.unrealized_plpc >= 0 ? "+" : ""}{pos.unrealized_plpc.toFixed(2)}%
                    </span>
                    <span className={`block text-xs tabular-nums ${plColor} opacity-70`}>
                      {pos.unrealized_pl >= 0 ? "+$" : "-$"}{Math.abs(pos.unrealized_pl).toLocaleString("en-US", { maximumFractionDigits: 0 })}
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        )}

        {/* Total row */}
        {hasPositions && (
          <div className="flex items-center justify-between pt-4 mt-1">
            <span className="text-xs text-gray-600 uppercase tracking-widest">Total</span>
            <div className="flex items-center gap-6 sm:gap-8">
              <span className="text-sm font-medium tabular-nums">
                ${totalValue.toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </span>
              <span
                className={`text-sm font-medium tabular-nums w-20 text-right ${
                  dailyPl >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {dailyPl >= 0 ? "+$" : "-$"}
                {Math.abs(dailyPl).toLocaleString("en-US", { maximumFractionDigits: 0 })}
              </span>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
