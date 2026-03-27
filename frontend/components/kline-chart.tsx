"use client";

import { createChart, ColorType, CrosshairMode } from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { Candle } from "../lib/api";

type KlineChartProps = {
  candles: Candle[];
  supportLevels?: number[];
  resistanceLevels?: number[];
  marketLabel?: string;
  timeframeLabel?: string;
  statusLabel?: string;
  emptyLabel?: string;
};

function toSeriesData(candles: Candle[]) {
  return candles.map((candle) => ({
    time: Math.floor(candle.open_time / 1000) as never,
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
  }));
}

function buildMovingAverage(candles: Candle[], period: number) {
  return candles.map((candle, index) => {
    const slice = candles.slice(Math.max(0, index - period + 1), index + 1);
    const average = slice.reduce((sum, item) => sum + item.close, 0) / slice.length;
    return {
      time: Math.floor(candle.open_time / 1000) as never,
      value: Number(average.toFixed(2)),
    };
  });
}

export function KlineChart({
  candles,
  supportLevels = [],
  resistanceLevels = [],
  marketLabel,
  timeframeLabel,
  statusLabel,
  emptyLabel = "等待 K 线数据。",
}: KlineChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) {
      return;
    }

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgba(255,255,255,0.72)",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.06)" },
        horzLines: { color: "rgba(255,255,255,0.06)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: "rgba(255,255,255,0.24)",
          labelBackgroundColor: "#31452d",
        },
        horzLine: {
          color: "rgba(255,255,255,0.18)",
          labelBackgroundColor: "#31452d",
        },
      },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.08)",
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.08)",
        timeVisible: true,
      },
      handleScroll: true,
      handleScale: true,
    });

    const series = chart.addCandlestickSeries({
      upColor: "#f3c15e",
      downColor: "#d96b44",
      wickUpColor: "#f3c15e",
      wickDownColor: "#d96b44",
      borderVisible: false,
      priceLineVisible: true,
      lastValueVisible: true,
    });

    series.setData(toSeriesData(candles));

    const ma20Series = chart.addLineSeries({
      color: "#f6df8b",
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    ma20Series.setData(buildMovingAverage(candles, 20));

    const ma60Series = chart.addLineSeries({
      color: "#8fd3c1",
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    ma60Series.setData(buildMovingAverage(candles, 60));

    const ma120Series = chart.addLineSeries({
      color: "#ff9b85",
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    ma120Series.setData(buildMovingAverage(candles, 120));

    for (const level of supportLevels) {
      series.createPriceLine({
        price: level,
        color: "rgba(143, 211, 193, 0.7)",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "支撑",
      });
    }

    for (const level of resistanceLevels) {
      series.createPriceLine({
        price: level,
        color: "rgba(255, 155, 133, 0.75)",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "阻力",
      });
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
    };
  }, [candles, resistanceLevels, supportLevels]);

  if (candles.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-[1.75rem] border border-white/10 bg-[linear-gradient(180deg,rgba(10,14,13,0.32),rgba(10,14,13,0.12))] px-5 py-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(243,193,94,0.16),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(143,211,193,0.12),transparent_28%)]" />
        <div className="relative flex min-h-72 flex-col justify-between gap-6 text-white/78">
          <div className="flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.22em] text-white/56">
            {marketLabel ? <span>{marketLabel}</span> : null}
            {timeframeLabel ? <span>{timeframeLabel}</span> : null}
            {statusLabel ? <span>{statusLabel}</span> : null}
          </div>
          <div className="max-w-md">
            <p className="text-sm uppercase tracking-[0.24em] text-white/45">图表</p>
            <p className="mt-3 text-lg leading-8 text-white/78">{emptyLabel}</p>
          </div>
          <div className="h-40 rounded-[1.25rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.01))]" />
        </div>
      </div>
    );
  }

  return (
    <div className="relative overflow-hidden rounded-[1.75rem] border border-white/10 bg-[linear-gradient(180deg,rgba(10,14,13,0.32),rgba(10,14,13,0.12))] px-5 py-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(243,193,94,0.16),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(143,211,193,0.12),transparent_28%)]" />
      <div className="relative mb-4 flex flex-wrap items-center justify-between gap-3 text-[11px] uppercase tracking-[0.22em] text-white/56">
        <div className="flex flex-wrap gap-2">
          {marketLabel ? <span>{marketLabel}</span> : null}
          {timeframeLabel ? <span>{timeframeLabel}</span> : null}
        </div>
        {statusLabel ? <span>{statusLabel}</span> : null}
      </div>
      <div ref={containerRef} className="relative h-72 w-full" />
    </div>
  );
}
