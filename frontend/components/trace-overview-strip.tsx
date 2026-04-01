import type { ReadableWorkflowOverview } from "../lib/api";

export function TraceOverviewStrip({ overview }: { overview: ReadableWorkflowOverview }) {
  const cards = [
    {
      label: "Trace Status",
      value: localizeStatus(overview.trace_status),
      tone: statusTone(overview.trace_status),
    },
    {
      label: "Total Tokens",
      value: formatNumber(overview.total_tokens),
      tone: tokenTone(overview.total_tokens),
    },
    {
      label: "LLM Calls",
      value: formatNumber(overview.llm_calls),
      tone: "neutral",
    },
    {
      label: "Tool Calls",
      value: formatNumber(overview.tool_calls),
      tone: "neutral",
    },
    {
      label: "Failures",
      value: formatNumber(overview.failures),
      tone: overview.failures > 0 ? "danger" : "neutral",
    },
    {
      label: "Total Duration",
      value: formatDuration(overview.total_duration_ms),
      tone: "neutral",
    },
  ] as const;

  return (
    <section className="rounded-[1.8rem] border border-black/10 bg-[linear-gradient(135deg,rgba(255,255,255,0.96),rgba(244,236,226,0.96))] p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Overview</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <article key={card.label} className={`rounded-[1.4rem] border p-4 ${toneClass(card.tone)}`}>
            <p className="text-[11px] uppercase tracking-[0.2em] text-black/45">{card.label}</p>
            <p className="mt-3 text-xl font-semibold text-black">{card.value}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function toneClass(tone: "neutral" | "warning" | "danger") {
  if (tone === "danger") {
    return "border-rose-300 bg-[linear-gradient(180deg,rgba(255,247,248,0.98),rgba(255,241,241,0.92))]";
  }
  if (tone === "warning") {
    return "border-amber-300 bg-[linear-gradient(180deg,rgba(255,251,240,0.98),rgba(255,246,224,0.92))]";
  }
  return "border-black/10 bg-white/78";
}

function tokenTone(totalTokens: number) {
  if (totalTokens > 20000) {
    return "danger";
  }
  if (totalTokens > 8000) {
    return "warning";
  }
  return "neutral";
}

function statusTone(status: string) {
  if (status === "failed" || status === "partial_failure") {
    return "danger";
  }
  if (status === "insufficient" || status === "cancelled") {
    return "warning";
  }
  return "neutral";
}

function localizeStatus(status: string) {
  if (status === "execute") {
    return "已执行";
  }
  if (status === "partial_failure") {
    return "Partial Failure";
  }
  if (status === "clarify") {
    return "待澄清";
  }
  if (status === "cancelled") {
    return "已取消";
  }
  if (status === "failed") {
    return "失败";
  }
  if (status === "insufficient") {
    return "证据不足";
  }
  if (status === "success") {
    return "成功";
  }
  return status || "未知";
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function formatDuration(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "无";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}s`;
  }
  return `${Math.round(value)}ms`;
}
