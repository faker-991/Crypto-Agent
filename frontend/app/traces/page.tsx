import Link from "next/link";

import { TraceRawEvents } from "../../components/trace-raw-events";
import { TraceReadableWorkflow } from "../../components/trace-readable-workflow";
import { fetchTrace, fetchTraceSummaries, type TracePayload } from "../../lib/api";

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
        <h2 className="mt-2 text-3xl font-semibold">可读执行流程</h2>
        {activeTrace ? (
          <>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <TraceTile label="时间" value={formatTimestamp(activeTrace.timestamp)} />
              <TraceTile
                label="状态"
                value={stringValue(activeTrace.status ?? getLegacyExecutionField(activeTrace.legacy_route, "type"))}
              />
              <TraceTile label="模式" value={stringValue(getPlanField(activeTrace.plan, "mode"))} />
              <TraceTile label="主 Agent" value={stringValue(inferLeadAgent(activeTrace))} />
              <TraceTile
                label="任务数"
                value={String((activeTrace.task_results?.length ?? getPlanTaskCount(activeTrace.plan)) || 0)}
              />
            </div>

            <div className="mt-5 rounded-[1.5rem] border border-black/10 bg-white/70 p-5 shadow-sm">
              <p className="text-xs uppercase tracking-[0.2em] text-black/45">用户问题</p>
              <p className="mt-2 text-sm leading-7 text-black/72">{activeTrace.user_query}</p>
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

function TraceTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.5rem] border border-black/10 bg-white/70 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-black/45">{label}</p>
      <p className="mt-3 text-sm text-black/75">{value}</p>
    </div>
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

function stringValue(value: unknown): string {
  if (typeof value === "string" && value.trim()) {
    return localizeStatus(value);
  }
  if (value === null || value === undefined) {
    return "无";
  }
  return String(value);
}

function getPlanField(plan: Record<string, unknown> | null | undefined, key: string): unknown {
  if (!plan || typeof plan !== "object") {
    return undefined;
  }
  return plan[key];
}

function getLegacyExecutionField(payload: Record<string, unknown> | null | undefined, key: string): unknown {
  if (!payload || typeof payload !== "object") {
    return undefined;
  }
  return payload[key];
}

function getPlanTaskCount(plan: Record<string, unknown> | null | undefined): number {
  const tasks = getPlanField(plan, "tasks");
  return Array.isArray(tasks) ? tasks.length : 0;
}

function inferLeadAgent(trace: TracePayload): string | undefined {
  const taskResults = trace.task_results;
  if (Array.isArray(taskResults) && taskResults.length) {
    const agent = taskResults[0]?.agent;
    if (typeof agent === "string" && agent.trim()) {
      return agent;
    }
  }
  const legacyAgent = getLegacyExecutionField(trace.legacy_route, "agent");
  if (typeof legacyAgent === "string" && legacyAgent.trim()) {
    return legacyAgent;
  }
  return undefined;
}

function localizeStatus(value: string | null | undefined) {
  if (!value) {
    return "未知";
  }
  if (value === "execute") {
    return "已执行";
  }
  if (value === "clarify") {
    return "待澄清";
  }
  if (value === "failed") {
    return "失败";
  }
  if (value === "success") {
    return "成功";
  }
  if (value === "insufficient") {
    return "证据不足";
  }
  if (value === "unknown") {
    return "未知";
  }
  return value;
}
