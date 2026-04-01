import Link from "next/link";

import { TraceAgentResults } from "../../components/trace-agent-results";
import { TraceRawEvents } from "../../components/trace-raw-events";
import { TraceReadableWorkflow } from "../../components/trace-readable-workflow";
import { TraceToolCalls } from "../../components/trace-tool-calls";
import { fetchTrace, fetchTraceSummaries } from "../../lib/api";

type TracesPageProps = {
  searchParams?: Promise<{ trace?: string }>;
};

export default async function TracesPage({ searchParams }: TracesPageProps) {
  const params = (await searchParams) ?? {};
  const traces = await fetchTraceSummaries();
  const activeId = params.trace ?? traces.items[0]?.id;
  const activeTrace = activeId ? await fetchTrace(activeId) : null;

  return (
    <main className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
      <section className="rounded-[2rem] border border-black/10 bg-white/75 p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-black/45">轨迹索引</p>
        <h2 className="mt-2 text-3xl font-semibold">执行记录</h2>
        <p className="mt-3 text-sm leading-7 text-black/65">
          浏览本地保存的 planner 与各个 agent 的执行记录。
        </p>
        <div className="mt-6 space-y-3">
          {traces.items.length ? (
            traces.items.map((trace) => {
              const isActive = trace.id === activeId;
              return (
                <Link
                  key={trace.id}
                  className={`block rounded-[1.5rem] border px-4 py-4 transition ${
                    isActive
                      ? "border-ink bg-[linear-gradient(135deg,rgba(18,17,24,0.96),rgba(52,42,30,0.9))] text-white"
                      : "border-black/10 bg-sand/70 hover:border-black/25"
                  }`}
                  href={`/traces?trace=${trace.id}`}
                  scroll
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className={`text-xs uppercase tracking-[0.2em] ${isActive ? "text-white/55" : "text-black/45"}`}>
                        {formatTimestamp(trace.timestamp)}
                      </p>
                      <h3 className="mt-2 text-sm font-semibold leading-6">{trace.user_query}</h3>
                    </div>
                    <span
                      className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${
                        isActive ? "bg-white/10 text-white/72" : "bg-white/80 text-black/55"
                      }`}
                    >
                      {localizeStatus(trace.status)}
                    </span>
                  </div>
                  <div
                    className={`mt-4 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.18em] ${
                      isActive ? "text-white/72" : "text-black/55"
                    }`}
                  >
                    {trace.agent ? <span>{trace.agent}</span> : null}
                    {trace.mode ? <span>{trace.mode}</span> : null}
                    {trace.task_count ? <span>{trace.task_count} 个任务</span> : null}
                  </div>
                </Link>
              );
            })
          ) : (
            <div className="rounded-[1.5rem] border border-black/10 bg-sand/70 p-4 text-sm text-black/65">
              还没有执行轨迹。先去首页跑一次 planner 流程。
            </div>
          )}
        </div>
      </section>

      <section className="rounded-[2rem] border border-black/10 bg-[linear-gradient(135deg,rgba(255,255,255,0.92),rgba(242,234,223,0.96))] p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-black/45">轨迹详情</p>
        <h2 className="mt-2 text-3xl font-semibold">时间线诊断</h2>
        {activeTrace ? (
          <>
            <div className="mt-5 rounded-[1.5rem] border border-black/10 bg-white/70 p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-black/45">用户问题</p>
                  <p className="mt-2 text-sm leading-7 text-black/72">{activeTrace.user_query}</p>
                </div>
                <div className="rounded-full border border-black/10 bg-white/80 px-3 py-2 text-[11px] uppercase tracking-[0.18em] text-black/55">
                  {formatTimestamp(activeTrace.timestamp)}
                </div>
              </div>
            </div>

            {buildLlmNotice(activeTrace) ? (
              <section className="mt-5 rounded-[1.5rem] border border-rose-300 bg-[linear-gradient(135deg,rgba(255,245,245,0.98),rgba(255,238,238,0.92))] p-5 shadow-sm">
                <p className="text-xs uppercase tracking-[0.2em] text-black/45">LLM 状态</p>
                <h2 className="mt-2 text-2xl font-semibold">本次回答层调用异常或已降级</h2>
                <div className="mt-4 space-y-2 text-sm leading-7 text-black/76">
                  <p>{buildLlmNotice(activeTrace)?.message}</p>
                  <p className="text-black/60">
                    模型：{buildLlmNotice(activeTrace)?.model ?? "未知"} · 提供方：
                    {buildLlmNotice(activeTrace)?.provider ?? "未知"} · 状态：
                    {buildLlmNotice(activeTrace)?.statusLabel ?? "未知"}
                  </p>
                </div>
              </section>
            ) : null}

            <section className="mt-5 rounded-[1.5rem] border border-black/10 bg-white/70 p-5 shadow-sm">
              <p className="text-xs uppercase tracking-[0.2em] text-black/45">Execution Metrics</p>
              <h2 className="mt-2 text-2xl font-semibold">Token、耗时与调用概览</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <PlanMetric label="Prompt Tokens" value={formatNumber(activeTrace.metrics_summary?.prompt_tokens)} />
                <PlanMetric label="Completion Tokens" value={formatNumber(activeTrace.metrics_summary?.completion_tokens)} />
                <PlanMetric label="Total Tokens" value={formatNumber(activeTrace.metrics_summary?.total_tokens)} />
                <PlanMetric label="LLM Calls" value={formatNumber(activeTrace.llm_call_count)} />
                <PlanMetric label="Tool Calls" value={formatNumber(activeTrace.tool_call_count)} />
              </div>
            </section>

            {activeTrace.plan ? (
              <section className="mt-5 rounded-[1.5rem] border border-black/10 bg-white/70 p-5 shadow-sm">
                <p className="text-xs uppercase tracking-[0.2em] text-black/45">Planner</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <PlanMetric label="模式" value={formatPlanField(activeTrace.plan["mode"])} />
                  <PlanMetric label="决策" value={formatPlanField(activeTrace.plan["decision_mode"])} />
                  <PlanMetric label="来源" value={formatPlanField(activeTrace.plan["planner_source"])} />
                </div>
                {Array.isArray(activeTrace.plan["tasks"]) && activeTrace.plan["tasks"].length ? (
                  <div className="mt-4 space-y-3">
                    {(activeTrace.plan["tasks"] as Array<Record<string, unknown>>).map((task, index) => (
                      <div
                        key={`${String(task["task_id"] ?? "task")}-${index}`}
                        className="rounded-[1.2rem] border border-black/10 bg-[#f8f3eb] p-4"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-[11px] uppercase tracking-[0.2em] text-black/40">
                              {formatPlanField(task["task_type"])}
                            </p>
                            <h3 className="mt-2 text-sm font-semibold leading-6 text-black/80">
                              {formatPlanField(task["title"])}
                            </h3>
                          </div>
                          <span className="rounded-full bg-white px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/55">
                            {formatPlanField(task["task_id"])}
                          </span>
                        </div>
                        {task["slots"] && typeof task["slots"] === "object" ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {Object.entries(task["slots"] as Record<string, unknown>).map(([key, value]) => (
                              <span
                                key={`${task["task_id"]}-${key}`}
                                className="rounded-full border border-black/10 bg-white/80 px-3 py-1 text-[11px] text-black/65"
                              >
                                {key}: {formatPlanField(value)}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>
            ) : null}

            <div className="mt-5">
              <TraceAgentResults taskResults={activeTrace.task_results} />
            </div>

            <div className="mt-5">
              <TraceToolCalls taskResults={activeTrace.task_results} />
            </div>

            {activeTrace.readable_workflow ? (
              <TraceReadableWorkflow workflow={activeTrace.readable_workflow} />
            ) : (
              <section className="mt-5 rounded-[1.5rem] border border-black/10 bg-white/70 p-5 shadow-sm">
                <p className="text-xs uppercase tracking-[0.2em] text-black/45">可读执行流程</p>
                <p className="mt-3 text-sm leading-7 text-black/68">
                  这条轨迹的结构化信息不足，暂时无法生成可读执行流程。
                </p>
              </section>
            )}

            <div className="mt-5">
              <TraceRawEvents events={activeTrace.events} />
            </div>
          </>
        ) : (
          <div className="mt-6 rounded-[1.5rem] border border-black/10 bg-white/70 p-5 text-sm text-black/65">
            请先从左侧选择一条轨迹查看。
          </div>
        )}
      </section>
    </main>
  );
}

function formatTimestamp(timestamp: string): string {
  if (!timestamp) {
    return "无";
  }
  const normalized = timestamp.replace(
    /(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})\d+Z/,
    "$1-$2-$3T$4:$5:$6Z",
  );
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function localizeStatus(value: string | null | undefined) {
  if (!value) {
    return "未知";
  }
  if (value === "partial_failure") {
    return "Partial Failure";
  }
  if (value === "execute") {
    return "已执行";
  }
  if (value === "clarify") {
    return "待澄清";
  }
  if (value === "cancelled") {
    return "已取消";
  }
  if (value === "failed") {
    return "失败";
  }
  if (value === "success") {
    return "成功";
  }
  if (value === "degraded") {
    return "已降级";
  }
  if (value === "insufficient") {
    return "证据不足";
  }
  if (value === "unknown") {
    return "未知";
  }
  return value;
}

function buildLlmNotice(activeTrace: Awaited<ReturnType<typeof fetchTrace>> | null) {
  if (!activeTrace?.spans?.length) {
    return null;
  }
  const answerSpan = [...activeTrace.spans]
    .reverse()
    .find((span) => span.name === "answer_generation" && span.kind === "llm");
  if (!answerSpan) {
    return null;
  }

  const provider = String(answerSpan.attributes?.provider ?? "");
  const model = String(answerSpan.attributes?.model ?? "");
  const error = typeof answerSpan.error === "string" && answerSpan.error ? answerSpan.error : null;
  const degraded = provider === "deterministic-fallback" || provider === "execution-summary";
  const failed = answerSpan.status === "failed";

  if (!failed && !degraded && !error) {
    return null;
  }

  return {
    message:
      error ??
      (degraded
        ? "远程回答层调用没有成功完成，系统已降级为本地确定性总结。"
        : "回答层 LLM 调用失败。"),
    model,
    provider,
    statusLabel: failed ? "失败" : degraded ? "已降级" : localizeStatus(answerSpan.status),
  };
}

function PlanMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.2rem] border border-black/10 bg-[#f8f3eb] p-4">
      <p className="text-[11px] uppercase tracking-[0.2em] text-black/40">{label}</p>
      <p className="mt-2 text-sm font-semibold text-black/78">{value}</p>
    </div>
  );
}

function formatPlanField(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "无";
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatPlanField(item)).join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat("zh-CN").format(value ?? 0);
}
