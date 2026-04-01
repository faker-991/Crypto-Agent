type TraceAgentResultsProps = {
  taskResults?: Array<Record<string, unknown>> | null;
};

export function TraceAgentResults({ taskResults }: TraceAgentResultsProps) {
  if (!taskResults?.length) {
    return null;
  }

  return (
    <section className="rounded-[1.6rem] border border-black/10 bg-white/75 p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Agent Outputs</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">各 Agent 输出结果</h3>
        </div>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/55">
          {taskResults.length} 个任务
        </span>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-3">
        {taskResults.map((task, index) => {
          const payload = asRecord(task.payload);
          const missingInformation = asStringList(task.missing_information);
          const summary =
            stringValue(task.summary) ||
            stringValue(payload.summary) ||
            stringValue(asRecord(payload.execution_summary).summary) ||
            "无摘要";
          return (
            <article key={`${stringValue(task.task_id) || "task"}-${index}`} className="rounded-[1.3rem] border border-black/10 bg-[#f8f3eb] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.2em] text-black/42">{stringValue(task.task_type) || "task"}</p>
                  <h4 className="mt-2 text-base font-semibold text-black/82">{stringValue(task.agent) || "unknown"}</h4>
                </div>
                <span className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${statusClass(stringValue(task.status))}`}>
                  {localizeStatus(stringValue(task.status))}
                </span>
              </div>

              <p className="mt-4 text-sm leading-7 text-black/72">{summary}</p>

              <div className="mt-4 flex flex-wrap gap-2">
                {typeof task.rounds_used === "number" ? <MiniPill label={`rounds ${task.rounds_used}`} /> : null}
                {typeof task.evidence_sufficient === "boolean" ? (
                  <MiniPill label={`evidence ${task.evidence_sufficient ? "充足" : "不足"}`} />
                ) : null}
                {missingInformation.length ? <MiniPill label={`missing ${missingInformation.length}`} /> : null}
              </div>

              {missingInformation.length ? (
                <div className="mt-4 rounded-[1rem] border border-amber-300/70 bg-amber-50/80 p-3">
                  <p className="text-[11px] uppercase tracking-[0.2em] text-amber-900/55">缺失信息</p>
                  <ul className="mt-2 space-y-1 text-sm leading-6 text-amber-950/75">
                    {missingInformation.map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function MiniPill({ label }: { label: string }) {
  return <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] text-black/62">{label}</span>;
}

function localizeStatus(status: string | null) {
  if (status === "success") return "成功";
  if (status === "failed") return "失败";
  if (status === "insufficient") return "证据不足";
  if (status === "degraded") return "已降级";
  return status || "未知";
}

function statusClass(status: string | null) {
  if (status === "failed") return "bg-rose-100 text-rose-700";
  if (status === "insufficient" || status === "degraded") return "bg-amber-100 text-amber-700";
  return "bg-emerald-100 text-emerald-700";
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}
