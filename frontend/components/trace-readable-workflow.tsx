import type { ReadableWorkflow } from "../lib/api";

export function TraceReadableWorkflow({
  workflow,
}: {
  workflow: ReadableWorkflow | null | undefined;
}) {
  if (!workflow) {
    return null;
  }

  return (
    <div className="mt-5 space-y-5">
      {workflow.final_conclusion ? <FinalConclusionCard conclusion={workflow.final_conclusion} /> : null}

      <section className="rounded-[1.5rem] border border-black/10 bg-white/70 p-5 shadow-sm">
        <p className="text-xs uppercase tracking-[0.2em] text-black/45">执行时间线</p>
        {workflow.timeline.length ? (
          <div className="mt-4 space-y-4">
            {workflow.timeline.map((stage, index) => (
              <StageCard key={`${stage.kind}-${index}`} index={index + 1} stage={stage} />
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm leading-7 text-black/68">当前这条轨迹没有可读的执行阶段信息。</p>
        )}
      </section>
    </div>
  );
}

function FinalConclusionCard({
  conclusion,
}: {
  conclusion: NonNullable<ReadableWorkflow["final_conclusion"]>;
}) {
  const hasMissing = conclusion.missing_information.length > 0;
  const isDegraded = Boolean(conclusion.degraded_reason);

  return (
    <section
      className={`rounded-[1.5rem] border p-5 shadow-sm ${
        isDegraded
          ? "border-rose-300 bg-[linear-gradient(180deg,rgba(255,247,248,0.98),rgba(255,241,241,0.92))]"
          : "border-black/10 bg-white/72"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-black/45">最终结论</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">这次执行得出了什么</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill
            label={
              conclusion.evidence_sufficient === true
                ? "证据充足"
                : conclusion.evidence_sufficient === false
                  ? "证据不足"
                  : localizeStatus(conclusion.status)
            }
            tone={conclusion.evidence_sufficient === false ? "warning" : "neutral"}
          />
          {isDegraded ? <StatusPill label="已降级" tone="danger" /> : null}
        </div>
      </div>

      {conclusion.summary ? <p className="mt-4 text-base leading-8 text-black/82">{conclusion.summary}</p> : null}

      {conclusion.final_answer && conclusion.final_answer !== conclusion.summary ? (
        <div className="mt-4 rounded-[1.3rem] border border-black/10 bg-sand/50 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-black/45">最终回答</p>
          <p className="mt-2 text-sm leading-7 text-black/76">{conclusion.final_answer}</p>
        </div>
      ) : null}

      {hasMissing ? (
        <div className="mt-4 rounded-[1.3rem] border border-rose-200 bg-rose-50/80 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-rose-700">证据缺口</p>
          <ul className="mt-3 space-y-2 text-sm leading-7 text-rose-900/80">
            {conclusion.missing_information.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {conclusion.degraded_reason ? (
        <div className="mt-4 rounded-[1.3rem] border border-rose-200 bg-rose-50/80 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-rose-700">降级原因</p>
          <p className="mt-2 text-sm leading-7 text-rose-900/80">{conclusion.degraded_reason}</p>
        </div>
      ) : null}
    </section>
  );
}

function StageCard({
  index,
  stage,
}: {
  index: number;
  stage: ReadableWorkflow["timeline"][number];
}) {
  const toneClass =
    stage.status === "failed"
      ? "border-rose-300 bg-[linear-gradient(180deg,rgba(255,247,248,0.98),rgba(255,241,241,0.92))]"
      : stage.status === "insufficient"
        ? "border-amber-300 bg-[linear-gradient(180deg,rgba(255,251,240,0.98),rgba(255,246,224,0.92))]"
        : "border-black/10 bg-white/72";

  const metaEntries = Object.entries(stage.meta ?? {}).filter(([key, value]) => {
    if (["loop_steps", "termination_reason", "loop_rounds"].includes(key)) {
      return false;
    }
    if (Array.isArray(value)) {
      return value.length > 0;
    }
    return value !== null && value !== undefined && String(value).trim() !== "";
  });

  return (
    <article className={`rounded-[1.5rem] border p-5 shadow-sm ${toneClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white">
            {index}
          </span>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-black/45">{localizeKind(stage.kind)}</p>
            <h4 className="mt-1 text-xl font-semibold text-black">{localizeStageTitle(stage.title, stage.kind)}</h4>
          </div>
        </div>
        <StatusPill
          label={localizeStatus(stage.status)}
          tone={stage.status === "failed" ? "danger" : stage.status === "insufficient" ? "warning" : "neutral"}
        />
      </div>

      {metaEntries.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {metaEntries.map(([key, value]) => (
            <div key={key} className="rounded-full border border-black/10 bg-white/70 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/62">
              {localizeMetaKey(key)}: {Array.isArray(value) ? value.join(", ") : String(value)}
            </div>
          ))}
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <StageSection title="做了什么" items={stage.did} />
        <StageSection title="实际调用" items={stage.actual_calls} />
        <StageSection title="查到什么" items={stage.found} />
        <StageSection title="输出结论" items={stage.conclusion} />
      </div>

      {stage.kind === "research" ? <ResearchLoopSection meta={stage.meta} /> : null}
    </article>
  );
}

function StageSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <section className="rounded-[1.25rem] border border-black/10 bg-white/60 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-black/45">{title}</p>
      <ul className="mt-3 space-y-2 text-sm leading-7 text-black/76">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function StatusPill({
  label,
  tone,
}: {
  label: string;
  tone: "neutral" | "warning" | "danger";
}) {
  const toneClass =
    tone === "danger"
      ? "border-rose-300 bg-rose-100 text-rose-700"
      : tone === "warning"
        ? "border-amber-300 bg-amber-100 text-amber-800"
        : "border-black/10 bg-white/80 text-black/60";

  return <span className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${toneClass}`}>{label}</span>;
}

function ResearchLoopSection({ meta }: { meta: Record<string, unknown> }) {
  const loopSteps = Array.isArray(meta.loop_steps) ? meta.loop_steps.filter((item): item is string => typeof item === "string") : [];
  if (!loopSteps.length) {
    return null;
  }

  const terminationReason =
    typeof meta.termination_reason === "string" && meta.termination_reason.trim() ? meta.termination_reason : null;

  return (
    <section className="mt-4 rounded-[1.25rem] border border-black/10 bg-white/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.2em] text-black/45">循环过程</p>
        {typeof meta.loop_rounds === "number" ? (
          <span className="rounded-full border border-black/10 bg-white/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/62">
            {meta.loop_rounds} 轮
          </span>
        ) : null}
      </div>
      <ul className="mt-3 space-y-2 text-sm leading-7 text-black/76">
        {loopSteps.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {terminationReason ? (
        <div className="mt-4 rounded-[1rem] border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm leading-7 text-amber-900/80">
          停止原因：{terminationReason}
        </div>
      ) : null}
    </section>
  );
}

function localizeStatus(status: string) {
  if (status === "success") {
    return "成功";
  }
  if (status === "insufficient") {
    return "证据不足";
  }
  if (status === "failed") {
    return "失败";
  }
  if (status === "skipped") {
    return "已跳过";
  }
  if (status === "execute") {
    return "已执行";
  }
  if (status === "clarify") {
    return "待澄清";
  }
  return "未知";
}

function localizeKind(kind: string) {
  if (kind === "planner") {
    return "规划";
  }
  if (kind === "research") {
    return "研究";
  }
  if (kind === "kline") {
    return "K 线";
  }
  if (kind === "summary") {
    return "总结";
  }
  return "其他";
}

function localizeStageTitle(title: string, kind: string) {
  if (kind === "planner") {
    return "Planner 规划";
  }
  if (kind === "research") {
    return "ResearchAgent 研究";
  }
  if (kind === "kline") {
    return "KlineAgent 分析";
  }
  if (kind === "summary") {
    return "SummaryAgent 汇总";
  }
  return title;
}

function localizeMetaKey(key: string) {
  if (key === "market_type") {
    return "市场类型";
  }
  if (key === "timeframes") {
    return "周期";
  }
  if (key === "planner_source") {
    return "规划来源";
  }
  if (key === "decision_mode") {
    return "决策模式";
  }
  if (key === "route_type") {
    return "路由类型";
  }
  if (key === "legacy") {
    return "旧版轨迹";
  }
  return key.replace(/_/g, " ");
}
