import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";

async function fetchAlpacaPositions(totalValue: number) {
  const base = (process.env.ALPACA_BASE_URL ?? "https://paper-api.alpaca.markets/v2").replace(/\/v2$/, "");
  const headers = {
    "APCA-API-KEY-ID": process.env.ALPACA_API_KEY!,
    "APCA-API-SECRET-KEY": process.env.ALPACA_SECRET_KEY!,
  };

  try {
    const resp = await fetch(`${base}/v2/positions`, { headers, cache: "no-store" });
    if (!resp.ok) return [];
    const positions = await resp.json();
    return positions.map((p: any) => ({
      ticker: p.symbol,
      shares: parseFloat(p.qty),
      entry_price: parseFloat(p.avg_entry_price),
      current_price: parseFloat(p.current_price),
      market_value: parseFloat(p.market_value),
      unrealized_pl: parseFloat(p.unrealized_pl),
      unrealized_plpc: parseFloat(p.unrealized_plpc) * 100,
      allocation_pct: totalValue > 0 ? (parseFloat(p.market_value) / totalValue) * 100 : 0,
    }));
  } catch {
    return [];
  }
}

export async function GET() {
  const [benchmarkResp, portfolioResp] = await Promise.all([
    supabase.from("benchmark").select("*").order("date", { ascending: true }),
    supabase.from("portfolio").select("*").order("last_updated", { ascending: false }).limit(1),
  ]);

  const portfolio = portfolioResp.data?.[0] ?? null;
  const totalValue = portfolio?.total_value ?? 100_000;
  const livePositions = await fetchAlpacaPositions(totalValue);

  return NextResponse.json({
    benchmark: benchmarkResp.data ?? [],
    portfolio,
    livePositions,
  });
}
