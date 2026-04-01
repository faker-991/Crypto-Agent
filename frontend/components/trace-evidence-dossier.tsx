"use client";

import type { TraceConclusion, TraceEvidenceRecord } from "../lib/api";

const GROUP_ORDER = ["technical", "market", "risk", "catalyst", "sentiment", "webpage", "search_result", "derived"] as const;

export function TraceEvidenceDossier({
  evidence,
  conclusions,
  selectedEvidenceIds,
  onSelectEvidence,
}: {
  evidence?: TraceEvidenceRecord[] | null;
  conclusions?: TraceConclusion[] | null;
  selectedEvidenceIds?: string[] | null;
  onSelectEvidence?: (evidenceId: string | null) => void;
}) {
  const items = evidence ?? [];
  const selectedSet = new Set(selectedEvidenceIds ?? []);

  if (!items.length) {
    return (
      <section className="rounded-[1.8rem] border border-black/10 bg-white/76 p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Evidence Dossier</p>
        <h3 className="mt-2 text-2xl font-semibold text-black">证据卷宗</h3>
        <p className="mt-4 text-sm leading-8 text-black/68">这条 trace 还没有可展示的证据记录，当前只能查看下方原始时间线。</p>
      </section>
    );
  }

  const grouped = GROUP_ORDER.map((group) => [group, items.filter((item) => item.type === group)] as const).filter(
    ([, groupItems]) => groupItems.length,
  );

  return (
    <section className="rounded-[1.8rem] border border-black/10 bg-[linear-gradient(135deg,rgba(255,255,255,0.94),rgba(245,239,231,0.95))] p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Evidence Dossier</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">来源、网站与提取证据</h3>
        </div>
        <span className="rounded-full border border-black/10 bg-white/80 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/58">
          {items.length} evidence items
        </span>
      </div>

      <div className="mt-5 space-y-5">
        {grouped.map(([group, groupItems]) => (
          <div key={group}>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-black/45">{localizeGroup(group)}</p>
            {group === "search_result" ? (
              <SearchEvidenceGroup
                conclusions={conclusions}
                items={groupItems}
                onSelectEvidence={onSelectEvidence}
                selectedSet={selectedSet}
              />
            ) : group === "webpage" ? (
              <FetchEvidenceGroup
                conclusions={conclusions}
                items={groupItems}
                onSelectEvidence={onSelectEvidence}
                selectedSet={selectedSet}
              />
            ) : (
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                {groupItems.map((item) => (
                  <EvidenceCard
                    key={item.evidence_id}
                    conclusions={conclusions}
                    item={item}
                    onSelectEvidence={onSelectEvidence}
                    selected={selectedSet.has(item.evidence_id)}
                  />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function SearchEvidenceGroup({
  items,
  conclusions,
  selectedSet,
  onSelectEvidence,
}: {
  items: TraceEvidenceRecord[];
  conclusions?: TraceConclusion[] | null;
  selectedSet: Set<string>;
  onSelectEvidence?: (evidenceId: string | null) => void;
}) {
  const parentRecords = items.filter((item) => typeof item.attributes?.result_count === "number");
  const childRecords = items.filter((item) => typeof item.attributes?.result_count !== "number");

  return (
    <div className="mt-3 space-y-3">
      {parentRecords.map((parent) => {
        const query = typeof parent.attributes?.query === "string" ? parent.attributes.query : parent.title;
        const relatedResults = childRecords.filter(
          (item) => (item.attributes?.query as string | undefined) === query,
        );
        return (
          <div key={parent.evidence_id} className="rounded-[1.35rem] border border-black/10 bg-white/82 p-4 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.18em] text-black/45">search query</p>
                <h4 className="mt-2 text-base font-semibold text-black">{query}</h4>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge label={`provider ${(parent.attributes?.provider as string | undefined) ?? "unknown"}`} />
                <Badge label={`results ${String(parent.attributes?.result_count ?? 0)}`} />
              </div>
            </div>

            <div className="mt-4 space-y-2">
              {relatedResults.map((item) => (
                <button
                  key={item.evidence_id}
                  className={`w-full rounded-[1.1rem] border px-3 py-3 text-left transition ${
                    selectedSet.has(item.evidence_id)
                      ? "border-black bg-[linear-gradient(135deg,rgba(18,17,24,0.96),rgba(52,42,30,0.9))] text-white"
                      : "border-black/10 bg-sand/35 text-black hover:border-black/25"
                  }`}
                  onClick={() => onSelectEvidence?.(item.evidence_id)}
                  type="button"
                >
                  <p className={`text-[11px] uppercase tracking-[0.18em] ${selectedSet.has(item.evidence_id) ? "text-white/55" : "text-black/45"}`}>
                    {item.source_domain ?? "website"}
                  </p>
                  <p className="mt-1 text-sm font-semibold">{item.title}</p>
                  {item.summary ? <p className={`mt-2 text-xs leading-6 ${selectedSet.has(item.evidence_id) ? "text-white/75" : "text-black/62"}`}>{item.summary}</p> : null}
                  {item.source_url ? <p className={`mt-2 break-all text-xs leading-6 ${selectedSet.has(item.evidence_id) ? "text-white/60" : "text-black/48"}`}>{item.source_url}</p> : null}
                  <div className="mt-2 flex flex-wrap gap-2">
                    {linkedConclusions(item, conclusions).map((label) => (
                      <Badge key={label} label={label} inverted={selectedSet.has(item.evidence_id)} />
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function FetchEvidenceGroup({
  items,
  conclusions,
  selectedSet,
  onSelectEvidence,
}: {
  items: TraceEvidenceRecord[];
  conclusions?: TraceConclusion[] | null;
  selectedSet: Set<string>;
  onSelectEvidence?: (evidenceId: string | null) => void;
}) {
  return (
    <div className="mt-3 grid gap-3 lg:grid-cols-2">
      {items.map((item) => (
        <button
          key={item.evidence_id}
          className={`rounded-[1.35rem] border p-4 text-left shadow-sm transition ${
            selectedSet.has(item.evidence_id)
              ? "border-black bg-[linear-gradient(135deg,rgba(18,17,24,0.96),rgba(52,42,30,0.9))] text-white"
              : "border-black/10 bg-white/82 hover:border-black/25"
          }`}
          onClick={() => onSelectEvidence?.(item.evidence_id)}
          type="button"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className={`text-[11px] uppercase tracking-[0.18em] ${selectedSet.has(item.evidence_id) ? "text-white/55" : "text-black/45"}`}>
                fetch result
              </p>
              <h4 className="mt-2 text-base font-semibold">{item.title}</h4>
            </div>
            {item.captured_at ? <Badge label={formatTimestamp(item.captured_at)} inverted={selectedSet.has(item.evidence_id)} /> : null}
          </div>

          {item.source_url ? <p className={`mt-3 break-all text-xs leading-6 ${selectedSet.has(item.evidence_id) ? "text-white/65" : "text-black/52"}`}>{item.source_url}</p> : null}
          {item.summary ? <p className={`mt-3 text-sm leading-7 ${selectedSet.has(item.evidence_id) ? "text-white/76" : "text-black/72"}`}>{item.summary}</p> : null}

          <div className="mt-3 flex flex-wrap gap-2">
            {typeof item.attributes?.strategy === "string" ? (
              <Badge label={`strategy ${item.attributes.strategy}`} inverted={selectedSet.has(item.evidence_id)} />
            ) : null}
            {typeof item.attributes?.failure_reason === "string" && item.attributes.failure_reason ? (
              <Badge label={`failure ${item.attributes.failure_reason}`} inverted={selectedSet.has(item.evidence_id)} />
            ) : null}
            {linkedConclusions(item, conclusions).map((label) => (
              <Badge key={label} label={label} inverted={selectedSet.has(item.evidence_id)} />
            ))}
          </div>
        </button>
      ))}
    </div>
  );
}

function EvidenceCard({
  item,
  conclusions,
  selected,
  onSelectEvidence,
}: {
  item: TraceEvidenceRecord;
  conclusions?: TraceConclusion[] | null;
  selected: boolean;
  onSelectEvidence?: (evidenceId: string | null) => void;
}) {
  return (
    <button
      className={`rounded-[1.35rem] border p-4 text-left shadow-sm transition ${
        selected
          ? "border-black bg-[linear-gradient(135deg,rgba(18,17,24,0.96),rgba(52,42,30,0.9))] text-white"
          : "border-black/10 bg-white/82 hover:border-black/25"
      }`}
      onClick={() => onSelectEvidence?.(item.evidence_id)}
      type="button"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className={`text-[11px] uppercase tracking-[0.18em] ${selected ? "text-white/55" : "text-black/45"}`}>
            {item.source_domain ?? item.source_tool ?? item.source_kind ?? "unknown"}
          </p>
          <h4 className="mt-2 text-base font-semibold">{item.title}</h4>
        </div>
        {item.captured_at ? <Badge label={formatTimestamp(item.captured_at)} inverted={selected} /> : null}
      </div>

      {item.summary ? <p className={`mt-3 text-sm leading-7 ${selected ? "text-white/76" : "text-black/72"}`}>{item.summary}</p> : null}

      <div className="mt-3 flex flex-wrap gap-2">
        {linkedConclusions(item, conclusions).map((label) => (
          <Badge key={label} label={label} inverted={selected} />
        ))}
        {renderEvidenceAttributes(item).map((label) => (
          <Badge key={label} label={label} inverted={selected} />
        ))}
      </div>
    </button>
  );
}

function renderEvidenceAttributes(item: TraceEvidenceRecord) {
  const attributes = item.attributes ?? {};
  const badges: string[] = [];

  if (typeof attributes.provider === "string" && attributes.provider) {
    badges.push(`provider ${attributes.provider}`);
  }
  if (typeof attributes.query === "string" && attributes.query) {
    badges.push(`query ${attributes.query}`);
  }
  if (typeof attributes.strategy === "string" && attributes.strategy) {
    badges.push(`strategy ${attributes.strategy}`);
  }
  if (typeof attributes.result_count === "number") {
    badges.push(`results ${attributes.result_count}`);
  }
  if (typeof attributes.failure_reason === "string" && attributes.failure_reason) {
    badges.push(`failure ${attributes.failure_reason}`);
  }
  if (typeof attributes.timeframe === "string" && attributes.timeframe) {
    badges.push(`timeframe ${attributes.timeframe}`);
  }

  return badges;
}

function linkedConclusions(item: TraceEvidenceRecord, conclusions?: TraceConclusion[] | null) {
  const matches =
    conclusions?.filter((conclusion) => (conclusion.evidence_ids ?? []).includes(item.evidence_id)).map((conclusion) => {
      return `${conclusion.kind} -> ${localizeStatus(conclusion.status)}`;
    }) ?? [];
  return matches;
}

function Badge({ label, inverted = false }: { label: string; inverted?: boolean }) {
  return (
    <span
      className={`rounded-full border px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${
        inverted ? "border-white/18 bg-white/10 text-white/80" : "border-black/10 bg-sand/55 text-black/58"
      }`}
    >
      {label}
    </span>
  );
}

function localizeGroup(group: string) {
  if (group === "technical") return "Technical";
  if (group === "market") return "Market";
  if (group === "risk") return "Risk";
  if (group === "catalyst") return "Catalyst";
  if (group === "sentiment") return "Sentiment";
  if (group === "webpage") return "Fetched Pages";
  if (group === "search_result") return "Search Results";
  return group;
}

function localizeStatus(status: string) {
  if (status === "partial_failure") return "Partial Failure";
  if (status === "failed") return "失败";
  if (status === "insufficient") return "证据不足";
  if (status === "success") return "成功";
  if (status === "execute") return "已执行";
  return status || "未知";
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}
