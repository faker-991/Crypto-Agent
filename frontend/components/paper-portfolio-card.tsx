import type { PaperPortfolio } from "../lib/api";

export function PaperPortfolioCard({ portfolio }: { portfolio: PaperPortfolio }) {
  return (
    <section className="rounded-3xl border border-black/10 bg-ink p-6 text-white shadow-sm">
      <h2 className="text-2xl font-semibold">Paper Portfolio</h2>
      <p className="mt-3 text-4xl">${portfolio.cash.toFixed(2)}</p>
      <p className="mt-1 text-sm text-white/70">Available cash</p>
      <div className="mt-5 space-y-3">
        {portfolio.positions.length === 0 ? (
          <p className="text-sm text-white/70">No open positions.</p>
        ) : (
          portfolio.positions.map((position) => (
            <div
              key={`${position.market_type}-${position.symbol}`}
              className="rounded-2xl border border-white/10 px-4 py-3"
            >
              <div className="flex items-center justify-between">
                <p className="font-semibold">{position.symbol}</p>
                <p className="text-sm uppercase text-white/70">{position.market_type}</p>
              </div>
              <p className="mt-2 text-sm text-white/70">
                Qty {position.quantity} @ ${position.average_entry_price}
              </p>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
