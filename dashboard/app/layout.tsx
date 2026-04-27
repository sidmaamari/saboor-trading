import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Saboor — Performance Dashboard",
  description: "Saboor autonomous halal trading agent vs S&P 500",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-[#0a0a0a] text-white min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
