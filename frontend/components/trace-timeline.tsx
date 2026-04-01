"use client";

import { useEffect, useMemo, useState } from "react";

import type { ReadableWorkflowMeta, TraceTimelineNode } from "../lib/api";
import { TraceDetailPanel } from "./trace-detail-panel";

type TimelineFilter = "all" | "failed" | "llm" | "tool";

const FILTERS: Array<{ key: TimelineFilter; label: string }> = [
  { key: "all", label: "All" },
  { key: "failed", label: "Failed Only" },
  { key: "llm", label: "LLM" },
  { key: "tool", label: "Tool" },
];

export function TraceTimeline({
  nodes,
  meta,
  externalSelectedId,
  onSelectedIdChange,
  highlightedSpanIds,
}: {
  nodes: TraceTimelineNode[];
  meta?: ReadableWorkflowMeta | null;
  externalSelectedId?: string | null;
  onSelectedIdChange?: (spanId: string | null) => void;
  highlightedSpanIds?: string[] | null;
}) {
  const normalizedNodes = nodes.map((node) => ({
    ...node,
    metrics: node.metrics ?? {},
  }));
  const [filter, setFilter] = useState<TimelineFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(
    normalizedNodes[0]?.span_id ?? null,
  );
  const highlightedSet = new Set(highlightedSpanIds ?? []);

  useEffect(() => {
    if (externalSelectedId) {
      setSelectedId(externalSelectedId);
    }
  }, [externalSelectedId]);

  const filteredNodes = useMemo(() => {
    return normalizedNodes.filter((node) => {
      if (filter === "failed") {
        return ["failed", "degraded", "insufficient"].includes(node.status);
      }
      if (filter === "llm") {
        return node.kind === "llm";
      }
      if (filter === "tool") {
        return node.kind === "tool";
      }
      return true;
    });
  }, [filter, normalizedNodes]);

  const selectedNode =
    filteredNodes.find((node) => node.span_id === selectedId) ??
    normalizedNodes.find((node) => node.span_id === selectedId) ??
    filteredNodes[0] ??
    null;

  useEffect(() => {
    if (!selectedNode) {
      setSelectedId(filteredNodes[0]?.span_id ?? null);
    }
  }, [filteredNodes, selectedNode]);

  return (
    <div className="space-y-5">
      <section className="rounded-[1.8rem] border border-black/10 bg-white/72 p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Timeline</p>
            <h3 className="mt-2 text-2xl font-semibold text-black">执行时间线</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((item) => (
              <button
                key={item.key}
                className={`rounded-full border px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] transition ${
                  filter === item.key
                    ? "border-black bg-ink text-white"
                    : "border-black/10 bg-white/80 text-black/62 hover:border-black/25"
                }`}
                onClick={() => setFilter(item.key)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5 space-y-3">
          {filteredNodes.length ? (
            filteredNodes.map((node, index) => {
              const selected = node.span_id === selectedNode?.span_id;
              return (
                <button
                  key={`${node.span_id || "timeline-node"}-${index}`}
                  className={`w-full rounded-[1.5rem] border p-4 text-left shadow-sm transition ${
                    selected
                      ? "border-black bg-[linear-gradient(135deg,rgba(18,17,24,0.96),rgba(52,42,30,0.9))] text-white"
                      : highlightedSet.has(node.span_id)
                        ? "border-amber-400 bg-[linear-gradient(135deg,rgba(255,250,238,0.98),rgba(255,244,221,0.92))] text-black"
                      : `${nodeTone(node.status)} hover:border-black/25`
                  }`}
                  onClick={() => {
                    setSelectedId(node.span_id);
                    onSelectedIdChange?.(node.span_id);
                  }}
                  type="button"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <span
                        className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold ${
                          selected ? "bg-white/12 text-white" : "bg-ink text-white"
                        }`}
                      >
                        {index + 1}
                      </span>
                      <div>
                        <p className={`text-[11px] uppercase tracking-[0.2em] ${selected ? "text-white/55" : "text-black/45"}`}>
                          {node.kind.toUpperCase()}
                        </p>
                        <h4 className="mt-1 text-lg font-semibold">{node.title}</h4>
                        <p className={`mt-2 text-sm leading-7 ${selected ? "text-white/74" : "text-black/68"}`}>{node.summary || "无摘要"}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <MetricBadge label={localizeStatus(node.status)} selected={selected} />
                      {typeof node.metrics.total_tokens === "number" ? (
                        <MetricBadge label={`${node.metrics.total_tokens} tok`} selected={selected} />
                      ) : null}
                      {typeof node.duration_ms === "number" ? (
                        <MetricBadge label={formatDuration(node.duration_ms)} selected={selected} />
                      ) : null}
                      {typeof node.metrics.output_bytes === "number" ? (
                        <MetricBadge label={`${node.metrics.output_bytes} bytes`} selected={selected} />
                      ) : null}
                    </div>
                  </div>
                </button>
              );
            })
          ) : (
            <div className="rounded-[1.4rem] border border-black/10 bg-sand/60 p-4 text-sm text-black/65">
              当前过滤器下没有时间线节点。
            </div>
          )}
        </div>
      </section>

      <TraceDetailPanel node={selectedNode} />
    </div>
  );
}

function MetricBadge({ label, selected }: { label: string; selected: boolean }) {
  return (
    <span
      className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${
        selected ? "border-white/18 bg-white/10 text-white/82" : "border-black/10 bg-white/80 text-black/60"
      }`}
    >
      {label}
    </span>
  );
}

function nodeTone(status: string) {
  if (status === "failed") {
    return "border-rose-300 bg-[linear-gradient(180deg,rgba(255,247,248,0.98),rgba(255,241,241,0.92))]";
  }
  if (status === "degraded" || status === "insufficient") {
    return "border-amber-300 bg-[linear-gradient(180deg,rgba(255,251,240,0.98),rgba(255,246,224,0.92))]";
  }
  return "border-black/10 bg-white/78";
}

function localizeStatus(status: string) {
  if (status === "failed") {
    return "失败";
  }
  if (status === "degraded") {
    return "已降级";
  }
  if (status === "insufficient") {
    return "证据不足";
  }
  if (status === "success") {
    return "成功";
  }
  return status || "未知";
}

function formatDuration(value: number) {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}s`;
  }
  return `${Math.round(value)}ms`;
}
