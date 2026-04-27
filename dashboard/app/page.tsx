import { supabase } from "@/lib/supabase";
import Dashboard from "@/components/Dashboard";

export const revalidate = 300;

async function getData() {
  const [benchmarkResp, portfolioResp, positionsResp] = await Promise.all([
    supabase.from("benchmark").select("*").order("date", { ascending: true }),
    supabase
      .from("portfolio")
      .select("*")
      .order("last_updated", { ascending: false })
      .limit(1),
    supabase.from("positions").select("*").eq("status", "open"),
  ]);

  return {
    benchmark: benchmarkResp.data ?? [],
    portfolio: portfolioResp.data?.[0] ?? null,
    openPositions: positionsResp.data ?? [],
  };
}

export default async function Home() {
  const data = await getData();
  return <Dashboard initial={data} />;
}
