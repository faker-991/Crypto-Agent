"use client";

import { useEffect, useMemo, useState } from "react";

import type { ReadableWorkflow } from "../lib/api";
import { TraceAuditAlerts } from "./trace-audit-alerts";
import { TraceConclusionDossier } from "./trace-conclusion-dossier";
import { TraceReasoningSteps } from "./trace-reasoning-steps";
import { TraceTimeline } from "./trace-timeline";

export function TraceReadableWorkflow({
  workflow,
}: {
  workflow: ReadableWorkflow | null | undefined;
}) {
  const [selectedConclusionId, setSelectedConclusionId] = useState<string | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedConclusionId(workflow?.conclusions?.[0]?.conclusion_id ?? null);
    setSelectedEvidenceId(null);
    setSelectedStepId(null);
    setSelectedSpanId(null);
  }, [workflow]);

  const selectedEvidenceIds = useMemo(() => {
    if (selectedEvidenceId) {
      return [selectedEvidenceId];
    }
    const selectedConclusion = (workflow?.conclusions ?? []).find((item) => item.conclusion_id === selectedConclusionId);
    return selectedConclusion?.evidence_ids ?? [];
  }, [selectedConclusionId, selectedEvidenceId, workflow?.conclusions]);

  const highlightedSpanIds = useMemo(() => {
    const evidenceSpans = (workflow?.evidence_records ?? [])
      .filter((item) => selectedEvidenceIds.includes(item.evidence_id))
      .map((item) => item.source_span_id)
      .filter((value): value is string => Boolean(value));
    const selectedStep = (workflow?.reasoning_steps ?? []).find((step) => step.step_id === selectedStepId);
    const stepSpans = [selectedStep?.llm_span_id, selectedStep?.tool_span_id].filter((value): value is string => Boolean(value));
    return Array.from(new Set([selectedSpanId, ...evidenceSpans, ...stepSpans].filter((value): value is string => Boolean(value))));
  }, [selectedEvidenceIds, selectedSpanId, selectedStepId, workflow?.evidence_records, workflow?.reasoning_steps]);

  if (!workflow) {
    return null;
  }

  return (
    <div className="mt-5 space-y-5">
      <TraceAuditAlerts
        onSelectSpan={setSelectedSpanId}
        steps={workflow.reasoning_steps}
        summary={workflow.audit_summary}
        timeline={workflow.timeline}
      />

      <section>
        <TraceConclusionDossier
          conclusions={workflow.conclusions}
          finalConclusion={workflow.final_conclusion}
          onSelectConclusion={(conclusionId) => {
            setSelectedConclusionId(conclusionId);
            setSelectedEvidenceId(null);
          }}
          selectedConclusionId={selectedConclusionId}
        />
      </section>

      <TraceReasoningSteps
        evidence={workflow.evidence_records}
        onSelectStep={(stepId) => {
          setSelectedStepId(stepId);
          const step = (workflow.reasoning_steps ?? []).find((item) => item.step_id === stepId);
          setSelectedSpanId(step?.tool_span_id ?? step?.llm_span_id ?? null);
        }}
        selectedStepId={selectedStepId}
        steps={workflow.reasoning_steps}
      />

      <TraceTimeline
        externalSelectedId={selectedSpanId}
        highlightedSpanIds={highlightedSpanIds}
        meta={workflow.meta}
        nodes={workflow.timeline ?? []}
        onSelectedIdChange={setSelectedSpanId}
      />
    </div>
  );
}
