"use client";

import type { TraceAuditSummary, TraceReasoningStep, TraceTimelineNode } from "../lib/api";

export function TraceAuditAlerts({
  summary,
  steps,
  timeline,
  onSelectSpan,
}: {
  summary?: TraceAuditSummary | null;
  steps?: TraceReasoningStep[] | null;
  timeline?: TraceTimelineNode[] | null;
  onSelectSpan?: (spanId: string | null) => void;
}) {
  const firstFailedStep = (steps ?? []).find((step) => ["failed", "degraded", "insufficient"].includes(step.status));
  const firstFailedNode = (timeline ?? []).find((node) => ["failed", "degraded", "insufficient"].includes(node.status));
  const firstError =
    firstFailedStep?.callback?.error ??
    firstFailedNode?.detail_tabs?.error?.error ??
    firstFailedNode?.summary ??
    null;

  const isTimeout = typeof firstError === "string" && /timed out|timeout/i.test(firstError);
  const shouldShow = Boolean(summary?.fallback_used || firstFailedStep || firstFailedNode || firstError);

  if (!shouldShow) {
    return null;
  }

  const toneClass = isTimeout
    ? "border-rose-300 bg-[linear-gradient(135deg,rgba(255,245,245,0.98),rgba(255,238,238,0.92))]"
    : "border-amber-300 bg-[linear-gradient(135deg,rgba(255,251,240,0.98),rgba(255,247,231,0.92))]";

  return (
    <section className={`rounded-[1.8rem] border p-5 shadow-sm ${toneClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Audit Alert</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">
            {isTimeout ? "LLM 调用超时或降级" : "本次执行存在异常或证据不足"}
          </h3>
        </div>
        {summary?.fallback_used ? (
          <span className="rounded-full border border-black/10 bg-white/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/58">
            fallback used
          </span>
        ) : null}
      </div>

      <div className="mt-4 space-y-3 text-sm leading-7 text-black/76">
        {firstError ? <p>{String(firstError)}</p> : null}
        {firstFailedStep ? (
          <p>
            首个异常步骤：`Step {firstFailedStep.round_index}` · {firstFailedStep.agent} ·{" "}
            {firstFailedStep.decision_summary}
          </p>
        ) : null}
        {firstFailedNode ? (
          <button
            className="rounded-full border border-black/10 bg-white/80 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-black/62 transition hover:border-black/25"
            onClick={() => onSelectSpan?.(firstFailedNode.span_id)}
            type="button"
          >
            跳到失败节点
          </button>
        ) : null}
      </div>
    </section>
  );
}
