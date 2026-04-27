import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function GET() {
  const [benchmarkResp, portfolioResp, positionsResp] = await Promise.all([
    supabase.from("benchmark").select("*").order("date", { ascending: true }),
    supabase
      .from("portfolio")
      .select("*")
      .order("last_updated", { ascending: false })
      .limit(1),
    supabase.from("positions").select("*").eq("status", "open"),
  ]);

  return NextResponse.json({
    benchmark: benchmarkResp.data ?? [],
    portfolio: portfolioResp.data?.[0] ?? null,
    openPositions: positionsResp.data ?? [],
  });
}
