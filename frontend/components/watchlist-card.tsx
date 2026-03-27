import type { Watchlist } from "../lib/api";

export function WatchlistCard({
  watchlist,
  onRemove,
}: {
  watchlist: Watchlist;
  onRemove?: (symbol: string) => void;
}) {
  return (
    <section className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-sm backdrop-blur">
      <h2 className="text-2xl font-semibold">Watchlist</h2>
      <div className="mt-4 space-y-3">
        {watchlist.assets.length === 0 ? (
          <p className="text-sm text-black/60">No assets tracked yet.</p>
        ) : (
          watchlist.assets.map((asset) => (
            <div
              key={asset.symbol}
              className="flex items-center justify-between rounded-2xl bg-sand px-4 py-3"
            >
              <div>
                <p className="text-lg font-semibold">{asset.symbol}</p>
                <p className="text-sm text-black/60">{asset.status}</p>
              </div>
              <div className="flex items-center gap-3">
                <p className="text-sm text-black/60">P{asset.priority}</p>
                {onRemove ? (
                  <button
                    className="rounded-full border border-black/10 px-3 py-1 text-xs text-black/70"
                    onClick={() => onRemove(asset.symbol)}
                    type="button"
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
