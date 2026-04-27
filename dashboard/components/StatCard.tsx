interface Props {
  label: string;
  value: string;
  sub?: string;
  color?: "green" | "blue" | "red" | "white";
}

const colors = {
  green: "text-green-400",
  blue: "text-blue-400",
  red: "text-red-400",
  white: "text-white",
};

export default function StatCard({ label, value, sub, color = "white" }: Props) {
  return (
    <div className="bg-[#111] border border-[#222] rounded-xl p-5">
      <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">{label}</p>
      <p className={`text-2xl font-semibold ${colors[color]}`}>{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-1">{sub}</p>}
    </div>
  );
}
