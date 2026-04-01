"use client";

import type { ReadableWorkflowConclusion, TraceConclusion } from "../lib/api";

export function TraceConclusionDossier({
  conclusions,
  finalConclusion,
  selectedConclusionId,
  onSelectConclusion,
}: {
  conclusions?: TraceConclusion[] | null;
  finalConclusion?: ReadableWorkflowConclusion | null;
  selectedConclusionId?: string | null;
  onSelectConclusion?: (conclusionId: string | null) => void;
}) {
  const primary = conclusions?.[0];
  const status = primary?.status ?? finalConclusion?.status ?? "unknown";
  const mainText = primary?.text ?? finalConclusion?.final_answer ?? finalConclusion?.summary ?? "";
  const summary = primary?.summary ?? finalConclusion?.summary ?? null;
  const missingInformation = primary?.missing_information ?? finalConclusion?.missing_information ?? [];
  const evidenceCount = primary?.evidence_ids?.length ?? 0;

  if (!primary && !finalConclusion) {
    return null;
  }

  return (
    <section className="rounded-[1.8rem] border border-black/10 bg-white/78 p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Conclusion Dossier</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">最终结论与证据关系</h3>
        </div>
        <span className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${statusTone(status)}`}>
          {localizeStatus(status)}
        </span>
      </div>

      {summary ? <p className="mt-4 text-sm leading-8 text-black/76">{summary}</p> : null}
      {mainText && mainText !== summary ? (
        <div className="mt-4 rounded-[1.3rem] border border-black/10 bg-sand/45 p-4 text-sm leading-8 text-black/78">
          {mainText}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${
            selectedConclusionId === (primary?.conclusion_id ?? "final")
              ? "border-black bg-ink text-white"
              : "border-black/10 bg-white/82 text-black/58"
          }`}
          onClick={() => onSelectConclusion?.(primary?.conclusion_id ?? "final")}
          type="button"
        >
          {`Conclusion ${primary?.kind ?? "final"}`}
        </button>
        <Badge label={`Evidence ${evidenceCount}`} />
        {primary?.derived_from_step_ids?.length ? <Badge label={`Steps ${primary.derived_from_step_ids.length}`} /> : null}
      </div>

      {missingInformation.length ? (
        <div className="mt-4 rounded-[1.3rem] border border-amber-300 bg-amber-50/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-800">Missing Information</p>
          <ul className="mt-3 space-y-2 text-sm leading-7 text-amber-950/80">
            {missingInformation.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {finalConclusion?.degraded_reason ? (
        <div className="mt-4 rounded-[1.3rem] border border-rose-300 bg-rose-50/80 p-4 text-sm leading-7 text-rose-900/82">
          {finalConclusion.degraded_reason}
        </div>
      ) : null}
    </section>
  );
}

function Badge({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-black/10 bg-white/82 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/58">
      {label}
    </span>
  );
}

function localizeStatus(status: string) {
  if (status === "execute") return "已执行";
  if (status === "partial_failure") return "Partial Failure";
  if (status === "failed") return "失败";
  if (status === "insufficient") return "证据不足";
  if (status === "cancelled") return "已取消";
  if (status === "success") return "成功";
  return status || "未知";
}

function statusTone(status: string) {
  if (status === "partial_failure" || status === "failed") {
    return "border-rose-300 bg-rose-100 text-rose-700";
  }
  if (status === "insufficient" || status === "cancelled") {
    return "border-amber-300 bg-amber-100 text-amber-800";
  }
  return "border-black/10 bg-white/80 text-black/60";
}
