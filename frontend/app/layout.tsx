import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Crypto Agent",
  description: "Personal crypto research agent skeleton",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto min-h-screen max-w-6xl px-6 py-10">
          <header className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.3em] text-black/50">Crypto Agent</p>
              <h1 className="mt-2 text-5xl font-semibold leading-none">Research and paper trades.</h1>
            </div>
            <nav className="flex gap-4 text-sm text-black/70">
              <Link href="/">Dashboard</Link>
              <Link href="/assets/BTC">Asset</Link>
              <Link href="/traces">Traces</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
