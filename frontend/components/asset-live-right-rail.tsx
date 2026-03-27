"use client";

import type { AssetLiveSnapshot } from "../lib/api";

type AssetLiveRightRailProps = {
  liveSnapshot: AssetLiveSnapshot | null;
};

export function AssetLiveRightRail({ liveSnapshot }: AssetLiveRightRailProps) {
  const ticker = liveSnapshot?.ticker_summary ?? null;
  const endpoint = liveSnapshot?.endpoint_summary ?? null;

  return (
    <aside className="space-y-6">
      <section className="rounded-[2rem] border border-black/10 bg-white/78 p-6 shadow-sm">
        <p className="text-xs uppercase tracking-[0.24em] text-black/42">实时行情</p>
        <h3 className="mt-2 text-2xl font-semibold text-black">当前市场读数</h3>
        {ticker ? (
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <StatTile label="最新价" value={formatPrice(ticker.last_price)} />
            <StatTile label="24h 涨跌" value={formatPercent(ticker.price_change_percent)} />
            <StatTile label="开盘价" value={formatPrice(ticker.open_price)} />
            <StatTile label="成交量" value={formatCompactNumber(ticker.volume)} />
            <StatTile label="买一" value={formatPrice(ticker.bid_price)} />
            <StatTile label="卖一" value={formatPrice(ticker.ask_price)} />
          </div>
        ) : (
          <p className="mt-5 text-sm leading-7 text-black/62">当前视图没有可用的 ticker 快照。</p>
        )}
      </section>

      <section className="rounded-[2rem] border border-black/10 bg-[linear-gradient(145deg,rgba(26,24,20,0.96),rgba(53,43,31,0.96))] p-6 text-white shadow-[0_18px_60px_rgba(20,18,14,0.14)]">
        <p className="text-xs uppercase tracking-[0.24em] text-white/45">数据来源</p>
        <h3 className="mt-2 text-2xl font-semibold">接口与状态</h3>
        <div className="mt-5 space-y-4">
          <DetailRow label="市场" value={localizeMarketType(liveSnapshot?.market_type)} />
          <DetailRow label="来源" value={liveSnapshot?.source === "binance" ? "Binance" : "不可用"} />
          <DetailRow label="交易对" value={liveSnapshot?.binance_symbol ?? "n/a"} />
          <DetailRow label="接口" value={endpoint?.url ?? "n/a"} />
          <DetailRow label="状态" value={liveSnapshot?.degraded_reason ?? "实时 Binance 数据可用"} />
        </div>
      </section>
    </aside>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.25rem] border border-black/10 bg-sand/60 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-black/42">{label}</p>
      <p className="mt-3 text-lg font-semibold text-black">{value}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-3 text-sm">
      <span className="text-white/48">{label}</span>
      <span className="max-w-[65%] text-right leading-7 text-white/84">{value}</span>
    </div>
  );
}

function localizeMarketType(value: string | null | undefined): string {
  if (value === "spot") {
    return "Binance 现货";
  }
  if (value === "futures" || value === "derivatives-trading-usds-futures") {
    return "Binance 合约";
  }
  return "未知";
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
