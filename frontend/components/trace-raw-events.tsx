import type { ReactNode } from "react";

import type { PlannerEvent } from "../lib/api";

export function TraceRawEvents({ events }: { events: PlannerEvent[] }) {
  return (
    <details className="rounded-[1.5rem] border border-black/10 bg-white/70 p-5 shadow-sm">
      <summary className="cursor-pointer text-sm font-semibold text-black">
        原始事件
        <span className="ml-2 text-xs font-normal uppercase tracking-[0.18em] text-black/45">{events.length} items</span>
      </summary>
      <div className="mt-4 space-y-3">
        {events.length ? (
          events.map((event, index) => (
            <div
              key={`${event.name}-${index}`}
              className={`rounded-[1.5rem] border p-4 shadow-sm ${
                isDegradedEvent(event.detail)
                  ? "border-rose-300 bg-[linear-gradient(180deg,rgba(255,247,248,0.98),rgba(255,241,241,0.92))]"
                  : "border-black/10 bg-white/72"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-black">{formatEventName(event.name)}</p>
                    <p className="text-xs uppercase tracking-[0.18em] text-black/45">{event.actor}</p>
                  </div>
                </div>
                {isDegradedEvent(event.detail) ? (
                  <span className="rounded-full border border-rose-300 bg-rose-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-700">
                    已降级
                  </span>
                ) : null}
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1fr]">
                <DetailSection title="输入" tone={isDegradedEvent(event.detail) ? "rose" : "sand"}>
                  <DetailList items={summarizeInput(event.detail)} emptyLabel="没有记录到结构化输入信息。" />
                </DetailSection>
                <DetailSection title="输出" tone={isDegradedEvent(event.detail) ? "rose" : "ink"}>
                  <DetailList items={summarizeOutput(event.detail)} emptyLabel="没有记录到结构化输出信息。" />
                </DetailSection>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {renderEventMeta(event.detail).map((item) => (
                  <div key={`${event.name}-${item.label}`} className="rounded-[1.5rem] border border-black/10 bg-white/70 p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-black/45">{item.label}</p>
                    <p className="mt-3 text-sm text-black/75">{item.value}</p>
                  </div>
                ))}
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-[1.5rem] border border-black/10 bg-white/70 p-4 text-sm text-black/65">
            这次执行没有产生事件记录。
          </div>
        )}
      </div>
    </details>
  );
}

function formatEventName(name: string): string {
  return name
    .split(".")
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" / ");
}

function isDegradedEvent(detail: Record<string, unknown> | undefined): boolean {
  return Boolean(detail?.degraded);
}

function stringValue(value: unknown): string {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (value === null || value === undefined) {
    return "无";
  }
  return String(value);
}

function summarizeInput(detail: Record<string, unknown>): Array<{ label: string; value: string }> {
  const summary: Array<{ label: string; value: string }> = [];
  const inputSummary = detail.input_summary;
  if (inputSummary && typeof inputSummary === "object" && !Array.isArray(inputSummary)) {
    const input = inputSummary as Record<string, unknown>;
    if (typeof input.asset === "string") {
      summary.push({ label: "标的", value: input.asset });
    }
    if (typeof input.timeframe === "string") {
      summary.push({ label: "周期", value: input.timeframe });
    }
    if (typeof input.market_type === "string") {
      summary.push({ label: "市场", value: input.market_type });
    }
  }
  const payload = detail.payload;
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const fields = payload as Record<string, unknown>;
    if (typeof fields.asset === "string" && !summary.some((item) => item.label === "标的")) {
      summary.push({ label: "标的", value: fields.asset });
    }
    if (Array.isArray(fields.timeframes) && fields.timeframes.length) {
      summary.push({ label: "周期", value: fields.timeframes.join(", ") });
    }
    if (typeof fields.market_type === "string" && !summary.some((item) => item.label === "市场")) {
      summary.push({ label: "市场", value: fields.market_type });
    }
  }
  if (typeof detail.request_type === "string") {
    summary.push({ label: "请求", value: detail.request_type });
  }
  if (typeof detail.mode === "string") {
    summary.push({ label: "模式", value: detail.mode });
  }
  if (typeof detail.task_id === "string") {
    summary.push({ label: "任务 ID", value: detail.task_id });
  }
  if (typeof detail.task_type === "string") {
    summary.push({ label: "任务类型", value: detail.task_type });
  }
  return summary;
}

function summarizeOutput(detail: Record<string, unknown>): Array<{ label: string; value: string }> {
  const summary: Array<{ label: string; value: string }> = [];
  const outputSummary = detail.output_summary;
  if (outputSummary && typeof outputSummary === "object" && !Array.isArray(outputSummary)) {
    const output = outputSummary as Record<string, unknown>;
    if (typeof output.source === "string") {
      summary.push({ label: "来源", value: output.source === "unavailable" ? "不可用" : output.source });
    }
    if (typeof output.market_type === "string") {
      summary.push({ label: "市场", value: output.market_type });
    }
    if (typeof output.endpoint === "string") {
      summary.push({ label: "接口", value: output.endpoint });
    }
    if (typeof output.answer === "string") {
      summary.push({ label: "回答", value: output.answer });
    }
    if (typeof output.error === "string") {
      summary.push({ label: "错误", value: output.error });
    }
  }
  if (detail.degraded) {
    summary.push({ label: "降级", value: stringValue(detail.error) });
  }
  if (typeof detail.decision_mode === "string") {
    summary.push({ label: "决策", value: detail.decision_mode });
  }
  if (typeof detail.planner_source === "string") {
    summary.push({ label: "规划来源", value: detail.planner_source });
  }
  if (Array.isArray(detail.agents_to_invoke) && detail.agents_to_invoke.length) {
    summary.push({ label: "执行 Agent", value: detail.agents_to_invoke.join(", ") });
  }
  if (typeof detail.task_count === "number") {
    summary.push({ label: "任务数", value: String(detail.task_count) });
  }
  if (typeof detail.task_id === "string" && !summary.some((item) => item.label === "任务 ID")) {
    summary.push({ label: "任务 ID", value: detail.task_id });
  }
  if (typeof detail.task_type === "string" && !summary.some((item) => item.label === "任务类型")) {
    summary.push({ label: "任务类型", value: detail.task_type });
  }
  return summary;
}

function renderEventMeta(detail: Record<string, unknown>): Array<{ label: string; value: string }> {
  const items: Array<{ label: string; value: string }> = [];
  if (typeof detail.integration === "string") {
    items.push({ label: "集成", value: detail.integration });
  }
  if (typeof detail.endpoint === "string") {
    items.push({ label: "接口", value: detail.endpoint });
  }
  if (detail.degraded !== undefined) {
    items.push({ label: "降级", value: detail.degraded ? "是" : "否" });
  }
  if (typeof detail.error === "string" && detail.error.trim()) {
    items.push({ label: "错误", value: detail.error });
  }
  if (typeof detail.request_type === "string") {
    items.push({ label: "请求", value: detail.request_type });
  }
  if (typeof detail.mode === "string") {
    items.push({ label: "模式", value: detail.mode });
  }
  if (typeof detail.decision_mode === "string") {
    items.push({ label: "决策", value: detail.decision_mode });
  }
  if (typeof detail.task_count === "number") {
    items.push({ label: "任务数", value: String(detail.task_count) });
  }
  return items;
}

function DetailSection({
  title,
  tone,
  children,
}: {
  title: string;
  tone: "rose" | "sand" | "ink";
  children: ReactNode;
}) {
  const toneClass =
    tone === "rose"
      ? "border-rose-200 bg-rose-50/80"
      : tone === "ink"
        ? "border-black/10 bg-white/70"
        : "border-black/10 bg-sand/40";

  return (
    <div className={`rounded-[1.3rem] border p-4 ${toneClass}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-black/45">{title}</p>
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function DetailList({
  items,
  emptyLabel,
}: {
  items: Array<{ label: string; value: string }>;
  emptyLabel: string;
}) {
  if (items.length === 0) {
    return <p className="text-sm leading-7 text-black/58">{emptyLabel}</p>;
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={`${item.label}-${item.value}`} className="flex items-start justify-between gap-4">
          <p className="text-xs uppercase tracking-[0.2em] text-black/42">{item.label}</p>
          <p className="max-w-[70%] text-right text-sm leading-6 text-black/76">{item.value}</p>
        </div>
      ))}
    </div>
  );
}
