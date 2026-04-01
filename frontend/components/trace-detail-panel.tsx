"use client";

import { useState } from "react";

import type { TraceTimelineNode } from "../lib/api";

const TAB_KEYS = ["input", "output", "error", "audit"] as const;
type TabKey = (typeof TAB_KEYS)[number];

export function TraceDetailPanel({ node }: { node: TraceTimelineNode | null }) {
  const [activeTab, setActiveTab] = useState<TabKey>("input");

  if (!node) {
    return (
      <section className="rounded-[1.6rem] border border-black/10 bg-white/72 p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Detail Panel</p>
        <p className="mt-3 text-sm leading-7 text-black/65">选择一个时间线节点后，这里会展开 `Input / Output / Error / Audit` 细节。</p>
      </section>
    );
  }

  const panel = node.detail_tabs?.[activeTab] ?? {};

  return (
    <section className="rounded-[1.6rem] border border-black/10 bg-[linear-gradient(135deg,rgba(255,255,255,0.94),rgba(245,239,231,0.95))] p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Detail Panel</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">{node.title}</h3>
          <p className="mt-2 text-sm leading-7 text-black/68">{node.summary || "这一步没有额外摘要。"} </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${statusTone(node.status)}`}>
          {localizeStatus(node.status)}
        </span>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {TAB_KEYS.map((tab) => (
          <button
            key={tab}
            className={`rounded-full border px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] transition ${
              activeTab === tab
                ? "border-black bg-ink text-white"
                : "border-black/10 bg-white/76 text-black/62 hover:border-black/25"
            }`}
            onClick={() => setActiveTab(tab)}
            type="button"
          >
            {tab.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="mt-5 rounded-[1.3rem] border border-black/10 bg-white/80 p-4">
        <pre className="overflow-x-auto whitespace-pre-wrap break-words text-sm leading-7 text-black/78">
          {JSON.stringify(panel, null, 2)}
        </pre>
      </div>
    </section>
  );
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

function statusTone(status: string) {
  if (status === "failed") {
    return "border-rose-300 bg-rose-100 text-rose-700";
  }
  if (status === "degraded" || status === "insufficient") {
    return "border-amber-300 bg-amber-100 text-amber-800";
  }
  return "border-black/10 bg-white/80 text-black/62";
}
