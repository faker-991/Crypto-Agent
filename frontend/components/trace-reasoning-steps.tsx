"use client";

import type { TraceEvidenceRecord, TraceReasoningStep } from "../lib/api";

export function TraceReasoningSteps({
  steps,
  evidence,
  selectedStepId,
  onSelectStep,
}: {
  steps?: TraceReasoningStep[] | null;
  evidence?: TraceEvidenceRecord[] | null;
  selectedStepId?: string | null;
  onSelectStep?: (stepId: string | null) => void;
}) {
  const items = steps ?? [];
  if (!items.length) {
    return null;
  }

  const evidenceMap = new Map((evidence ?? []).map((item) => [item.evidence_id, item]));

  return (
    <section className="rounded-[1.8rem] border border-black/10 bg-white/76 p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Reasoning Steps</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">ReAct 推理步骤</h3>
        </div>
        <span className="rounded-full border border-black/10 bg-white/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/58">
          {items.length} steps
        </span>
      </div>

      <div className="mt-5 space-y-4">
        {items.map((step) => (
          <button
            key={step.step_id}
            className={`w-full rounded-[1.4rem] border p-4 text-left ${selectedStepId === step.step_id ? "border-black bg-[linear-gradient(135deg,rgba(18,17,24,0.96),rgba(52,42,30,0.9))] text-white" : stepTone(step.status)}`}
            onClick={() => onSelectStep?.(step.step_id)}
            type="button"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className={`text-[11px] uppercase tracking-[0.18em] ${selectedStepId === step.step_id ? "text-white/55" : "text-black/45"}`}>
                  {step.agent} · Step {step.round_index}
                </p>
                <h4 className="mt-2 text-lg font-semibold">{step.decision_summary || "No decision summary"}</h4>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge label={localizeStatus(step.status)} inverted={selectedStepId === step.step_id} />
                {step.action ? <Badge label={step.action} inverted={selectedStepId === step.step_id} /> : null}
                {typeof step.duration_ms === "number" ? <Badge label={formatDuration(step.duration_ms)} inverted={selectedStepId === step.step_id} /> : null}
                {step.callback?.finish_reason ? <Badge label={step.callback.finish_reason} inverted={selectedStepId === step.step_id} /> : null}
              </div>
            </div>

            {step.args && Object.keys(step.args).length ? (
              <div className={`mt-4 rounded-[1.2rem] border p-3 ${selectedStepId === step.step_id ? "border-white/12 bg-white/8" : "border-black/10 bg-white/70"}`}>
                <p className={`text-[11px] uppercase tracking-[0.18em] ${selectedStepId === step.step_id ? "text-white/55" : "text-black/45"}`}>Args</p>
                <pre className={`mt-2 overflow-x-auto whitespace-pre-wrap break-words text-sm leading-7 ${selectedStepId === step.step_id ? "text-white/75" : "text-black/72"}`}>
                  {JSON.stringify(step.args, null, 2)}
                </pre>
              </div>
            ) : null}

            {step.observation_summary ? (
              <p className={`mt-4 text-sm leading-7 ${selectedStepId === step.step_id ? "text-white/76" : "text-black/72"}`}>{step.observation_summary}</p>
            ) : null}

            {step.new_evidence_ids?.length ? (
              <div className="mt-4">
                <p className={`text-[11px] uppercase tracking-[0.18em] ${selectedStepId === step.step_id ? "text-white/55" : "text-black/45"}`}>New Evidence</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {step.new_evidence_ids.map((evidenceId) => (
                    <Badge key={evidenceId} label={evidenceMap.get(evidenceId)?.title ?? evidenceId} inverted={selectedStepId === step.step_id} />
                  ))}
                </div>
              </div>
            ) : null}

            {step.callback ? (
              <div className={`mt-4 rounded-[1.2rem] border p-3 ${selectedStepId === step.step_id ? "border-white/12 bg-white/8" : "border-black/10 bg-sand/42"}`}>
                <p className={`text-[11px] uppercase tracking-[0.18em] ${selectedStepId === step.step_id ? "text-white/55" : "text-black/45"}`}>Callback</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {step.callback.started_at ? <Badge label={`start ${formatTimestamp(step.callback.started_at)}`} inverted={selectedStepId === step.step_id} /> : null}
                  {step.callback.first_token_at ? (
                    <Badge label={`first token ${formatTimestamp(step.callback.first_token_at)}`} inverted={selectedStepId === step.step_id} />
                  ) : null}
                  {step.callback.completed_at ? <Badge label={`done ${formatTimestamp(step.callback.completed_at)}`} inverted={selectedStepId === step.step_id} /> : null}
                  {step.callback.failed_at ? <Badge label={`failed ${formatTimestamp(step.callback.failed_at)}`} inverted={selectedStepId === step.step_id} /> : null}
                  {step.callback.error ? <Badge label={`error ${step.callback.error}`} inverted={selectedStepId === step.step_id} /> : null}
                </div>
              </div>
            ) : null}
          </button>
        ))}
      </div>
    </section>
  );
}

function Badge({ label, inverted = false }: { label: string; inverted?: boolean }) {
  return (
    <span className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${inverted ? "border-white/18 bg-white/10 text-white/82" : "border-black/10 bg-white/82 text-black/58"}`}>
      {label}
    </span>
  );
}

function stepTone(status: string) {
  if (status === "failed") {
    return "border-rose-300 bg-[linear-gradient(180deg,rgba(255,247,248,0.98),rgba(255,241,241,0.92))]";
  }
  if (status === "degraded" || status === "insufficient") {
    return "border-amber-300 bg-[linear-gradient(180deg,rgba(255,251,240,0.98),rgba(255,246,224,0.92))]";
  }
  return "border-black/10 bg-white/80";
}

function localizeStatus(status: string) {
  if (status === "partial_failure") return "Partial Failure";
  if (status === "failed") return "失败";
  if (status === "degraded") return "已降级";
  if (status === "insufficient") return "证据不足";
  if (status === "success") return "成功";
  return status || "未知";
}

function formatDuration(value: number) {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}s`;
  }
  return `${Math.round(value)}ms`;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString("zh-CN", { hour12: false });
}
