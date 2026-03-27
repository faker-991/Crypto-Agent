"use client";

import type { AssetDiscoveryItem, WatchlistItem } from "../lib/api";

type AssetSelectorProps = {
  currentSymbol: string;
  watchlist: WatchlistItem[];
  topAssets: AssetDiscoveryItem[];
  topAssetsError: string | null;
  searchQuery: string;
  searchResults: AssetDiscoveryItem[];
  searchError: string | null;
  isSearching: boolean;
  onSearchQueryChange: (value: string) => void;
  onSelectAsset: (symbol: string) => void;
  onAddToWatchlist: (symbol: string) => Promise<void>;
  onRemoveFromWatchlist: (symbol: string) => Promise<void>;
};

export function AssetSelector({
  currentSymbol,
  watchlist,
  topAssets,
  topAssetsError,
  searchQuery,
  searchResults,
  searchError,
  isSearching,
  onSearchQueryChange,
  onSelectAsset,
  onAddToWatchlist,
  onRemoveFromWatchlist,
}: AssetSelectorProps) {
  const watchlistSymbols = new Set(watchlist.map((item) => item.symbol.toUpperCase()));

  return (
    <section className="rounded-[1.8rem] border border-black/10 bg-white/78 p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-black/42">资产选择器</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">自选 + 默认前 20</h3>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-black/66">
            可以切换当前资产，也可以从搜索结果里加入自选。搜索结果只返回币安可交易资产，只有当前选中的资产会每秒刷新。
          </p>
        </div>
        <div className="min-w-[280px] flex-1">
          <input
            className="w-full rounded-[1.2rem] border border-black/10 bg-white px-4 py-3 text-sm text-black outline-none transition focus:border-black/25 focus:ring-2 focus:ring-black/5"
            onChange={(event) => onSearchQueryChange(event.target.value)}
            placeholder="搜索币安可交易资产，例如 BTC、DOGE、SOL"
            value={searchQuery}
          />
        </div>
      </div>

      <section className="mt-5">
        <p className="text-xs uppercase tracking-[0.2em] text-black/42">当前自选</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {watchlist.length ? (
            watchlist.map((item) => {
              const active = item.symbol.toUpperCase() === currentSymbol.toUpperCase();
              return (
                <div
                  key={item.symbol}
                  className={`flex items-center gap-2 rounded-full border px-3 py-2 text-sm ${
                    active ? "border-black bg-black text-white" : "border-black/10 bg-white text-black/78"
                  }`}
                >
                  <button className="font-medium" onClick={() => onSelectAsset(item.symbol)} type="button">
                    {item.symbol}
                  </button>
                  <button
                    className={`text-[11px] uppercase tracking-[0.18em] ${
                      active ? "text-white/60" : "text-black/45"
                    }`}
                    onClick={() => void onRemoveFromWatchlist(item.symbol)}
                    type="button"
                  >
                    移除
                  </button>
                </div>
              );
            })
          ) : (
            <p className="text-sm leading-7 text-black/58">当前还没有自选资产，可以从搜索结果或默认前 20 里添加。</p>
          )}
        </div>
      </section>

      <section className="mt-6">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs uppercase tracking-[0.2em] text-black/42">搜索结果</p>
          {isSearching ? <span className="text-xs text-black/45">搜索中...</span> : null}
        </div>
        {searchError ? (
          <div className="mt-3 rounded-[1.2rem] border border-rose-200 bg-rose-50/80 px-4 py-3 text-sm text-rose-700">
            {searchError}
          </div>
        ) : null}
        {searchQuery.trim() ? (
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {searchResults.length ? (
              searchResults.map((item) => {
                const inWatchlist = watchlistSymbols.has(item.symbol.toUpperCase());
                return (
                  <AssetResultCard
                    key={`search-${item.symbol}`}
                    actionLabel={inWatchlist ? "已在自选" : item.is_binance_supported ? "加入自选" : "不支持"}
                    disabled={!item.is_binance_supported || inWatchlist}
                    item={item}
                    onAction={() => void onAddToWatchlist(item.symbol)}
                    onSelect={() => onSelectAsset(item.symbol)}
                  />
                );
              })
            ) : (
              <div className="rounded-[1.2rem] border border-black/10 bg-sand/70 p-4 text-sm text-black/58">
                没有找到可展示的搜索结果。
              </div>
            )}
          </div>
        ) : null}
      </section>

      <section className="mt-6">
        <p className="text-xs uppercase tracking-[0.2em] text-black/42">默认前 20</p>
        {topAssetsError ? (
          <div className="mt-3 rounded-[1.2rem] border border-rose-200 bg-rose-50/80 px-4 py-3 text-sm leading-7 text-rose-700">
            {topAssetsError}
          </div>
        ) : null}
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {topAssets.length ? (
            topAssets.map((item) => {
              const inWatchlist = watchlistSymbols.has(item.symbol.toUpperCase());
              return (
                <AssetResultCard
                  key={`top-${item.symbol}`}
                  actionLabel={inWatchlist ? "已在自选" : item.is_binance_supported ? "加入自选" : "不支持"}
                  disabled={!item.is_binance_supported || inWatchlist}
                  item={item}
                  onAction={() => void onAddToWatchlist(item.symbol)}
                  onSelect={() => onSelectAsset(item.symbol)}
                />
              );
            })
          ) : topAssetsError ? null : (
            <div className="rounded-[1.2rem] border border-black/10 bg-sand/70 p-4 text-sm text-black/58">
              暂时没有拿到默认前 20。
            </div>
          )}
        </div>
      </section>
    </section>
  );
}

function AssetResultCard({
  item,
  actionLabel,
  disabled,
  onAction,
  onSelect,
}: {
  item: AssetDiscoveryItem;
  actionLabel: string;
  disabled: boolean;
  onAction: () => void;
  onSelect: () => void;
}) {
  return (
    <div className="rounded-[1.35rem] border border-black/10 bg-white/80 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <button className="text-left" onClick={onSelect} type="button">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              {item.rank !== null ? (
                <span className="rounded-full bg-black/6 px-2 py-1 text-[11px] uppercase tracking-[0.18em] text-black/55">
                  #{item.rank}
                </span>
              ) : null}
              <p className="text-sm font-semibold text-black">{item.display_name_zh ?? item.name ?? item.symbol}</p>
              <p className="text-xs text-black/52">{item.symbol}</p>
            </div>
            {item.display_name_zh && item.name && item.display_name_zh !== item.name ? (
              <p className="mt-1 text-xs text-black/52">{item.name}</p>
            ) : null}
          </button>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${
            item.is_binance_supported ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
          }`}
        >
          {item.is_binance_supported ? "可画图" : "不支持"}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 text-xs text-black/58">
        {item.current_price !== null ? <span>价格 {formatPrice(item.current_price)}</span> : null}
        {item.market_cap !== null ? <span>市值 {formatCompactNumber(item.market_cap)}</span> : null}
        {item.price_change_percentage_24h !== null ? (
          <span className={item.price_change_percentage_24h >= 0 ? "text-emerald-700" : "text-rose-700"}>
            24h {formatPercent(item.price_change_percentage_24h)}
          </span>
        ) : null}
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <button
          className="rounded-full border border-black/10 bg-white px-4 py-2 text-xs uppercase tracking-[0.18em] text-black/62 transition hover:border-black/25"
          onClick={onSelect}
          type="button"
        >
          打开
        </button>
        <button
          className="rounded-full bg-black px-4 py-2 text-xs uppercase tracking-[0.18em] text-white disabled:cursor-not-allowed disabled:opacity-45"
          disabled={disabled}
          onClick={onAction}
          type="button"
        >
          {actionLabel}
        </button>
      </div>
    </div>
  );
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 6,
  }).format(value);
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}
