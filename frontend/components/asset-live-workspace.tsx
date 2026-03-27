"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import {
  addWatchlistItem,
  fetchLiveAsset,
  fetchTopAssets,
  fetchWatchlist,
  removeWatchlistItem,
  searchAssets,
  type AssetDiscoveryItem,
  type AssetLiveSnapshot,
  type MarketType,
  type WatchlistItem,
} from "../lib/api";
import { AssetLiveRightRail } from "./asset-live-right-rail";
import { AssetSelector } from "./asset-selector";
import { KlineChart } from "./kline-chart";

const TIMEFRAMES = ["1m", "5m", "15m", "1h"] as const;

type AssetLiveWorkspaceProps = {
  initialSymbol: string;
  initialMarketType: MarketType;
  initialTimeframe: string;
};

export function AssetLiveWorkspace({
  initialSymbol,
  initialMarketType,
  initialTimeframe,
}: AssetLiveWorkspaceProps) {
  const router = useRouter();
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [topAssets, setTopAssets] = useState<AssetDiscoveryItem[]>([]);
  const [topAssetsError, setTopAssetsError] = useState<string | null>(null);
  const [liveSnapshot, setLiveSnapshot] = useState<AssetLiveSnapshot | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<AssetDiscoveryItem[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  const [isSearching, startSearchTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      const [watchlistPayload, topPayload] = await Promise.all([fetchWatchlist(), fetchTopAssets()]);
      setWatchlist(watchlistPayload.assets);
      setTopAssets(topPayload.items);
      setTopAssetsError(topPayload.error);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadLiveSnapshot() {
      const payload = await fetchLiveAsset(initialSymbol, initialMarketType, initialTimeframe);
      if (!cancelled) {
        setLiveSnapshot(payload);
      }
    }

    void loadLiveSnapshot();
    const timer = window.setInterval(() => {
      void loadLiveSnapshot();
    }, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [initialMarketType, initialSymbol, initialTimeframe]);

  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setSearchError(null);
      return;
    }

    const timer = window.setTimeout(() => {
      startSearchTransition(async () => {
        const payload = await searchAssets(searchQuery);
        setSearchResults(payload.items);
        setSearchError(payload.error);
      });
    }, 250);

    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  const headlineAsset = useMemo(() => {
    return (
      topAssets.find((item) => item.symbol === initialSymbol.toUpperCase()) ??
      searchResults.find((item) => item.symbol === initialSymbol.toUpperCase()) ??
      null
    );
  }, [initialSymbol, searchResults, topAssets]);

  async function handleAddToWatchlist(symbol: string) {
    const payload = await addWatchlistItem({ symbol, status: "watch", priority: 2 });
    setWatchlist(payload.assets);
  }

  async function handleRemoveFromWatchlist(symbol: string) {
    const payload = await removeWatchlistItem(symbol);
    setWatchlist(payload.assets);
  }

  function handleNavigate(symbol: string, marketType = initialMarketType, timeframe = initialTimeframe) {
    const params = new URLSearchParams({ market: marketType, timeframe });
    router.push(`/assets/${encodeURIComponent(symbol.toUpperCase())}?${params.toString()}`);
  }

  const chartSummary = liveSnapshot?.chart_summary ?? null;
  const ticker = liveSnapshot?.ticker_summary ?? null;
  const isUnavailable = !liveSnapshot?.is_supported || liveSnapshot?.source === "unavailable";

  return (
    <main className="space-y-6">
      <AssetSelector
        currentSymbol={initialSymbol}
        isSearching={isSearching}
        onAddToWatchlist={handleAddToWatchlist}
        onRemoveFromWatchlist={handleRemoveFromWatchlist}
        onSearchQueryChange={setSearchQuery}
        onSelectAsset={(symbol) => handleNavigate(symbol)}
        searchError={searchError}
        searchQuery={searchQuery}
        searchResults={searchResults}
        topAssetsError={topAssetsError}
        topAssets={topAssets}
        watchlist={watchlist}
      />

      <section className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
        <section className="space-y-6">
          <div className="overflow-hidden rounded-[2.25rem] border border-black/10 bg-[linear-gradient(135deg,rgba(17,23,19,0.96),rgba(33,29,22,0.96))] p-6 text-white shadow-[0_24px_80px_rgba(20,18,14,0.18)]">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-white/45">资产工作台</p>
                <h2 className="mt-3 text-4xl font-semibold tracking-tight">{initialSymbol.toUpperCase()}</h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-white/72">
                  {headlineAsset?.display_name_zh ??
                    headlineAsset?.name ??
                    liveSnapshot?.name ??
                    "当前选中资产"}
                  ，当前只刷新这一只资产的实时价格和图表。
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs uppercase tracking-[0.2em] text-white/70">
                <Badge tone="amber">{liveSnapshot?.source === "binance" ? "实时 Binance 数据" : "实时数据不可用"}</Badge>
                <Badge tone={isUnavailable ? "rose" : "moss"}>{isUnavailable ? "不可用" : "健康"}</Badge>
                <Badge tone="slate">{liveSnapshot?.binance_symbol ?? "n/a"}</Badge>
              </div>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <StatTile label="最新价" value={formatPrice(ticker?.last_price)} />
              <StatTile label="24h 涨跌" value={formatPercent(ticker?.price_change_percent)} />
              <StatTile label="24h 成交量" value={formatCompactNumber(ticker?.volume)} />
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              {(["spot", "futures"] as const).map((marketType) => (
                <NavChip
                  key={marketType}
                  active={initialMarketType === marketType}
                  label={marketType === "spot" ? "Binance 现货" : "Binance 合约"}
                  onClick={() => handleNavigate(initialSymbol, marketType, initialTimeframe)}
                />
              ))}
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              {TIMEFRAMES.map((timeframe) => (
                <NavChip
                  key={timeframe}
                  active={initialTimeframe === timeframe}
                  label={timeframe.toUpperCase()}
                  onClick={() => handleNavigate(initialSymbol, initialMarketType, timeframe)}
                />
              ))}
            </div>

            <div className="mt-6">
              <KlineChart
                candles={liveSnapshot?.candles ?? []}
                emptyLabel={liveSnapshot?.degraded_reason ?? "当前周期没有返回任何 K 线数据。"}
                marketLabel={describeMarketType(liveSnapshot?.market_type ?? initialMarketType)}
                resistanceLevels={chartSummary?.resistance_levels ?? []}
                statusLabel={isUnavailable ? "不可用" : "实时"}
                supportLevels={chartSummary?.support_levels ?? []}
                timeframeLabel={`${initialTimeframe} 视图`}
              />
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <StatTile label="趋势" value={localizeTrend(chartSummary?.trend_regime)} />
              <StatTile label="突破" value={chartSummary?.breakout_signal ? "关注突破" : "暂时平静"} />
              <StatTile label="回撤" value={localizeDrawdown(chartSummary?.drawdown_state)} />
            </div>

            {chartSummary?.conclusion ? (
              <div className="mt-5 rounded-[1.4rem] border border-white/10 bg-white/8 p-4 text-sm leading-7 text-white/78">
                {chartSummary.conclusion}
              </div>
            ) : null}
          </div>
        </section>

        <AssetLiveRightRail liveSnapshot={liveSnapshot} />
      </section>
    </main>
  );
}

function Badge({
  tone,
  children,
}: {
  tone: "amber" | "rose" | "moss" | "slate";
  children: ReactNode;
}) {
  const toneClass =
    tone === "amber"
      ? "bg-amber-300/15 text-amber-100 ring-amber-200/25"
      : tone === "rose"
        ? "bg-rose-400/12 text-rose-100 ring-rose-200/25"
        : tone === "moss"
          ? "bg-emerald-400/12 text-emerald-100 ring-emerald-200/20"
          : "bg-white/10 text-white/72 ring-white/10";
  return <span className={`rounded-full px-3 py-1 ring-1 ${toneClass}`}>{children}</span>;
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.3rem] border border-white/10 bg-white/6 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-white/45">{label}</p>
      <p className="mt-3 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function NavChip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`rounded-full px-4 py-2 text-xs uppercase tracking-[0.2em] transition ${
        active
          ? "bg-white text-black"
          : "bg-white/10 text-white/72 ring-1 ring-white/10 hover:bg-white/16"
      }`}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}

function describeMarketType(value: string): string {
  if (value === "futures" || value === "derivatives-trading-usds-futures") {
    return "Binance 合约";
  }
  return "Binance 现货";
}

function localizeTrend(value: string | undefined): string {
  if (value === "uptrend") {
    return "上升趋势";
  }
  if (value === "downtrend") {
    return "下降趋势";
  }
  if (value === "range") {
    return "区间震荡";
  }
  if (value === "unavailable") {
    return "不可用";
  }
  return "n/a";
}

function localizeDrawdown(value: string | undefined): string {
  if (value === "near-high") {
    return "靠近高位";
  }
  if (value === "reaccumulation") {
    return "再积累";
  }
  if (value === "deep-drawdown") {
    return "深度回撤";
  }
  if (value === "unavailable") {
    return "不可用";
  }
  return "n/a";
}

function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 6,
  }).format(value);
}

function formatCompactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}
