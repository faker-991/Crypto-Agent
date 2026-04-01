import type { TraceAuditSummary } from "../lib/api";

export function TraceAuditSummary({ summary }: { summary?: TraceAuditSummary | null }) {
  if (!summary) {
    return null;
  }

  const cards = [
    {
      label: "Trace Status",
      value: localizeStatus(summary.trace_status),
      tone: statusTone(summary.trace_status),
    },
    {
      label: "Duration",
      value: formatDuration(summary.duration_ms),
      tone: "neutral",
    },
    {
      label: "Total Tokens",
      value: formatNumber(summary.total_tokens),
      tone: tokenTone(summary.total_tokens),
    },
    {
      label: "LLM Calls",
      value: formatNumber(summary.llm_calls),
      tone: "neutral",
    },
    {
      label: "Tool Calls",
      value: formatNumber(summary.tool_calls),
      tone: "neutral",
    },
    {
      label: "Failures",
      value: `${formatNumber(summary.failed_calls)} / ${formatNumber(summary.degraded_calls)}`,
      tone: (summary.failed_calls ?? 0) > 0 ? "danger" : (summary.degraded_calls ?? 0) > 0 ? "warning" : "neutral",
    },
    {
      label: "Models Used",
      value: (summary.models_used ?? []).length ? (summary.models_used ?? []).join(", ") : "无",
      tone: "neutral",
    },
    {
      label: "Fallback Used",
      value: summary.fallback_used ? "Yes" : "No",
      tone: summary.fallback_used ? "warning" : "neutral",
    },
  ] as const;

  return (
    <section className="rounded-[1.8rem] border border-black/10 bg-[linear-gradient(135deg,rgba(255,255,255,0.97),rgba(242,233,219,0.96))] p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Audit Overview</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">执行审计总览</h3>
        </div>
        <div className="rounded-full border border-black/10 bg-white/80 px-3 py-2 text-[11px] uppercase tracking-[0.18em] text-black/55">
          {formatTimestamp(summary.started_at)} {summary.providers_used?.length ? `· ${summary.providers_used.join(", ")}` : ""}
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <article key={card.label} className={`rounded-[1.35rem] border p-4 ${toneClass(card.tone)}`}>
            <p className="text-[11px] uppercase tracking-[0.2em] text-black/45">{card.label}</p>
            <p className="mt-3 text-lg font-semibold text-black">{card.value}</p>
          </article>
        ))}
      </div>

      {summary.callback_summary ? (
        <div className="mt-5 rounded-[1.35rem] border border-black/10 bg-white/78 p-4 text-sm leading-7 text-black/70">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-black/45">LLM Callback</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <MiniBadge label={`started ${formatNumber(summary.callback_summary.started_count)}`} />
            <MiniBadge label={`completed ${formatNumber(summary.callback_summary.completed_count)}`} />
            <MiniBadge label={`failed ${formatNumber(summary.callback_summary.failed_count)}`} />
            <MiniBadge
              label={`first token ${formatDuration(summary.callback_summary.first_token_latency_ms_avg)}`}
            />
            {(summary.callback_summary.finish_reasons ?? []).map((reason) => (
              <MiniBadge key={reason} label={reason} />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function MiniBadge({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-black/10 bg-sand/55 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/60">
      {label}
    </span>
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

function tokenTone(totalTokens: number | null | undefined) {
  if ((totalTokens ?? 0) > 20000) {
    return "danger";
  }
  if ((totalTokens ?? 0) > 8000) {
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
  if (status === "execute") return "已执行";
  if (status === "partial_failure") return "Partial Failure";
  if (status === "clarify") return "待澄清";
  if (status === "cancelled") return "已取消";
  if (status === "failed") return "失败";
  if (status === "insufficient") return "证据不足";
  if (status === "success") return "成功";
  return status || "未知";
}

function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat("zh-CN").format(value ?? 0);
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

function formatTimestamp(timestamp: string | null | undefined) {
  if (!timestamp) {
    return "无时间";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}
