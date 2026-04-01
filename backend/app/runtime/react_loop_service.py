from __future__ import annotations

import json
from typing import Any

from app.runtime.tool_contracts import ToolResult, ToolSpec
from app.runtime.tool_runtime import ToolRuntime
from app.runtime.trace_runtime import TraceRuntime


class ReActLoopService:
    def __init__(
        self,
        *,
        llm_client: Any,
        tool_runtime: ToolRuntime,
        trace_runtime: TraceRuntime,
        observation_builder: Any | None = None,
        missing_information_builder: Any | None = None,
        evidence_sufficiency_checker: Any | None = None,
        max_rounds: int = 6,
        max_same_call_repeats: int = 1,
        max_tool_failures: int = 2,
        max_no_progress_rounds: int = 2,
        agent_name: str = "ResearchAgent",
    ) -> None:
        self.llm_client = llm_client
        self.tool_runtime = tool_runtime
        self.trace_runtime = trace_runtime
        self.observation_builder = observation_builder
        self.missing_information_builder = missing_information_builder
        self.evidence_sufficiency_checker = evidence_sufficiency_checker
        self.max_rounds = max_rounds
        self.max_same_call_repeats = max_same_call_repeats
        self.max_tool_failures = max_tool_failures
        self.max_no_progress_rounds = max_no_progress_rounds
        self.agent_name = agent_name

    def run(
        self,
        *,
        asset: str,
        tool_specs: list[ToolSpec],
        initial_context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[ToolResult]]:
        context = dict(initial_context or {})
        trace_id = str(context.get("trace_id") or f"react-{asset.lower()}")
        allowed_specs = {
            spec["name"]: spec
            for spec in tool_specs
            if spec.get("domain") in {"research", "market", "kline"} and spec.get("name")
        }
        observations: list[dict[str, Any]] = []
        tool_results: list[ToolResult] = []
        agent_loop: list[dict[str, Any]] = []
        successful_tools: list[str] = []
        failed_tools: list[str] = []
        degraded_reasons: list[str] = []
        last_call_signature: str | None = None
        same_call_repeats = 0
        tool_failures = 0
        no_progress_rounds = 0
        termination_reason: str | None = None
        terminal_status = "insufficient"
        evidence_status = "insufficient"

        for round_number in range(1, self.max_rounds + 1):
            llm_input = self._build_llm_input(
                asset=asset,
                round_number=round_number,
                allowed_specs=list(allowed_specs.values()),
                context=context,
                observations=observations,
                tool_results=tool_results,
            )
            llm_span = self.trace_runtime.start_span(
                trace_id=trace_id,
                parent_span_id=None,
                kind="llm",
                name=f"research_round_{round_number}",
                input_summary={
                    "asset": asset,
                    "round": round_number,
                    "available_tools": sorted(allowed_specs),
                },
                attributes={
                    "agent": self.agent_name,
                    "round": round_number,
                    "model": self._resolve_model_name(None),
                    "provider": self._resolve_provider_name(None),
                    "temperature": self._resolve_temperature(None),
                },
            )

            response = self._invoke_llm(llm_input)
            content = self._extract_content(response)
            metrics = self._usage_metrics(response)
            llm_attributes = {
                "model": self._resolve_model_name(response),
                "provider": self._resolve_provider_name(response),
                "temperature": self._resolve_temperature(response),
                "fallback_error": self._resolve_fallback_error(response),
            }
            if content is None:
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="failed",
                    output_summary={},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes=llm_attributes,
                    error="llm_response_missing_content",
                )
                termination_reason = "llm_response_missing_content"
                terminal_status = "failed"
                evidence_status = "failed"
                break

            try:
                step = json.loads(content)
            except json.JSONDecodeError:
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="failed",
                    output_summary={},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes=llm_attributes,
                    error="invalid_json",
                )
                termination_reason = "invalid_json"
                terminal_status = "failed"
                evidence_status = "failed"
                break

            required_fields = {"decision_summary", "action", "args", "termination", "termination_reason"}
            if not isinstance(step, dict) or not required_fields.issubset(step):
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="failed",
                    output_summary={},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes=llm_attributes,
                    error="missing_required_fields",
                )
                termination_reason = "missing_required_fields"
                terminal_status = "failed"
                evidence_status = "failed"
                break

            action = step.get("action")
            args = step.get("args")
            termination = bool(step.get("termination"))
            step_termination_reason = step.get("termination_reason")
            decision_summary = str(step.get("decision_summary") or "").strip()

            if not isinstance(args, dict):
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="failed",
                    output_summary={"decision_summary": decision_summary},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes={
                        **llm_attributes,
                        "decision_summary": decision_summary,
                        "action": action,
                        "termination_reason": step_termination_reason,
                    },
                    error="args_must_be_object",
                )
                termination_reason = "args_must_be_object"
                terminal_status = "failed"
                evidence_status = "failed"
                break

            if termination and action:
                degraded_reasons.append("conflicting_llm_step")
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="degraded",
                    output_summary={"decision_summary": decision_summary},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes={
                        **llm_attributes,
                        "decision_summary": decision_summary,
                        "action": action,
                        "termination_reason": step_termination_reason,
                        "degraded_reason": "conflicting_llm_step",
                    },
                    error="conflicting_llm_step",
                )
                termination_reason = str(step_termination_reason or "conflicting_llm_step")
                terminal_status = "insufficient"
                evidence_status = "insufficient"
                agent_loop.append(
                    self._build_agent_loop_entry(
                        round_number=round_number,
                        decision_summary=decision_summary,
                        action=action,
                        args=args,
                        tool_result=tool_results[-1] if tool_results else None,
                        termination_reason=termination_reason,
                        degraded_reason="conflicting_llm_step",
                    )
                )
                break

            if termination and not action:
                step_status = "success"
                if not self._is_evidence_sufficient(context=context, observations=observations):
                    step_status = "insufficient"
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status=step_status,
                    output_summary={"decision_summary": decision_summary},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes={
                        **llm_attributes,
                        "decision_summary": decision_summary,
                        "action": action,
                        "termination_reason": step_termination_reason,
                    },
                )
                termination_reason = str(step_termination_reason or "model_requested_stop")
                agent_loop.append(
                    self._build_agent_loop_entry(
                        round_number=round_number,
                        decision_summary=decision_summary,
                        action=action,
                        args=args,
                        tool_result=None,
                        termination_reason=termination_reason,
                    )
                )
                break

            if not termination and (not isinstance(action, str) or not action.strip()):
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="failed",
                    output_summary={"decision_summary": decision_summary},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes={
                        **llm_attributes,
                        "decision_summary": decision_summary,
                        "action": action,
                        "termination_reason": step_termination_reason,
                    },
                    error="empty_action",
                )
                termination_reason = "empty_action"
                terminal_status = "failed"
                evidence_status = "failed"
                break

            normalized_action = action.strip()
            spec = allowed_specs.get(normalized_action)
            if spec is None:
                degraded_reasons.append("unknown_tool")
                no_progress_rounds += 1
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="degraded",
                    output_summary={"decision_summary": decision_summary},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes={
                        **llm_attributes,
                        "decision_summary": decision_summary,
                        "action": normalized_action,
                        "termination_reason": step_termination_reason,
                        "degraded_reason": "unknown_tool",
                    },
                    error="unknown_tool",
                )
                agent_loop.append(
                    self._build_agent_loop_entry(
                        round_number=round_number,
                        decision_summary=decision_summary,
                        action=normalized_action,
                        args=args,
                        tool_result=None,
                        degraded_reason="unknown_tool",
                    )
                )
                if no_progress_rounds >= self.max_no_progress_rounds:
                    termination_reason = "no_progress_threshold_reached"
                    terminal_status = "insufficient"
                    evidence_status = "insufficient"
                    break
                continue

            if not self._validate_args(spec, args):
                degraded_reasons.append("schema_invalid_args")
                no_progress_rounds += 1
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="degraded",
                    output_summary={"decision_summary": decision_summary},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes={
                        **llm_attributes,
                        "decision_summary": decision_summary,
                        "action": normalized_action,
                        "termination_reason": step_termination_reason,
                        "degraded_reason": "schema_invalid_args",
                    },
                    error="schema_invalid_args",
                )
                agent_loop.append(
                    self._build_agent_loop_entry(
                        round_number=round_number,
                        decision_summary=decision_summary,
                        action=normalized_action,
                        args=args,
                        tool_result=None,
                        degraded_reason="schema_invalid_args",
                    )
                )
                if no_progress_rounds >= self.max_no_progress_rounds:
                    termination_reason = "no_progress_threshold_reached"
                    terminal_status = "insufficient"
                    evidence_status = "insufficient"
                    break
                continue

            call_signature = self._call_signature(normalized_action, args)
            if call_signature == last_call_signature:
                same_call_repeats += 1
            else:
                same_call_repeats = 0
            last_call_signature = call_signature

            if same_call_repeats > self.max_same_call_repeats:
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="degraded",
                    output_summary={"decision_summary": decision_summary},
                    metrics=metrics,
                    audit={"actor": self.agent_name},
                    attributes={
                        **llm_attributes,
                        "decision_summary": decision_summary,
                        "action": normalized_action,
                        "termination_reason": step_termination_reason,
                        "degraded_reason": "repeated_identical_call",
                    },
                    error="repeated_identical_call",
                )
                degraded_reasons.append("repeated_identical_call")
                termination_reason = "repeated_identical_call"
                terminal_status = "insufficient"
                evidence_status = "insufficient"
                agent_loop.append(
                    self._build_agent_loop_entry(
                        round_number=round_number,
                        decision_summary=decision_summary,
                        action=normalized_action,
                        args=args,
                        tool_result=None,
                        termination_reason=termination_reason,
                        degraded_reason="repeated_identical_call",
                    )
                )
                break

            self.trace_runtime.finish_span(
                span_id=llm_span["span_id"],
                status="success",
                output_summary={"decision_summary": decision_summary, "action": normalized_action},
                metrics=metrics,
                audit={"actor": self.agent_name},
                attributes={
                    **llm_attributes,
                    "decision_summary": decision_summary,
                    "action": normalized_action,
                    "termination_reason": step_termination_reason,
                },
            )

            evidence_before = self._evidence_markers(observations)
            tool_result, observation, made_progress = self._execute_tool(
                trace_id=trace_id,
                llm_span_id=llm_span["span_id"],
                tool_name=normalized_action,
                args=args,
                spec=spec,
            )
            if tool_result is not None:
                tool_results.append(tool_result)
            if tool_result is not None and tool_result["status"] == "failed":
                tool_failures += 1
                failed_tools.append(normalized_action)
                self.trace_runtime.finish_span(
                    span_id=llm_span["span_id"],
                    status="failed",
                    output_summary={"decision_summary": decision_summary, "action": normalized_action},
                    audit={"actor": self.agent_name},
                    attributes={"tool_execution_failed": True},
                    error=tool_result.get("error"),
                )
            elif tool_result is not None and tool_result["status"] == "degraded":
                degraded_reasons.append(str(tool_result.get("reason") or normalized_action))
            else:
                successful_tools.append(normalized_action)

            if observation is not None:
                observations.append(observation)

            if self._has_new_evidence(evidence_before, observations, observation, made_progress):
                no_progress_rounds = 0
            else:
                no_progress_rounds += 1

            current_missing = self._derive_missing_information(context=context, observations=observations)
            agent_loop.append(
                self._build_agent_loop_entry(
                    round_number=round_number,
                    decision_summary=decision_summary,
                    action=normalized_action,
                    args=args,
                    tool_result=tool_result,
                    termination_reason=None,
                    missing_information=current_missing,
                )
            )

            if tool_failures > self.max_tool_failures:
                termination_reason = "tool_failure_threshold_exceeded"
                terminal_status = "failed"
                evidence_status = "failed"
                agent_loop[-1]["termination"] = {"reason": termination_reason}
                break

            if no_progress_rounds >= self.max_no_progress_rounds:
                termination_reason = "no_progress_threshold_reached"
                terminal_status = "insufficient"
                evidence_status = "insufficient"
                agent_loop[-1]["termination"] = {"reason": termination_reason}
                break

            if self._is_evidence_sufficient(context=context, observations=observations):
                termination_reason = "Evidence threshold met."
                terminal_status = "success"
                evidence_status = "sufficient"
                agent_loop[-1]["termination"] = {"reason": termination_reason}
                break
        else:
            termination_reason = "max_rounds_reached"
            terminal_status = "insufficient"
            evidence_status = "insufficient"

        final_missing = self._derive_missing_information(context=context, observations=observations)
        if evidence_status != "failed":
            evidence_status = "sufficient" if self._is_evidence_sufficient(context=context, observations=observations) else "insufficient"
            if terminal_status == "success" and evidence_status != "sufficient":
                terminal_status = "insufficient"
            elif terminal_status == "insufficient" and evidence_status == "sufficient":
                terminal_status = "success"

        terminal_state = {
            "asset": asset,
            "status": terminal_status,
            "evidence_status": evidence_status,
            "termination_reason": termination_reason,
            "rounds_used": len(agent_loop),
            "observations": observations,
            "successful_tools": list(dict.fromkeys(successful_tools)),
            "failed_tools": list(dict.fromkeys(failed_tools)),
            "missing_information": final_missing,
            "degraded_reasons": list(dict.fromkeys(reason for reason in degraded_reasons if reason)),
            "agent_loop": agent_loop,
        }
        return terminal_state, observations, tool_results

    def _invoke_llm(self, payload: dict[str, Any]) -> Any:
        for method_name in ("complete", "chat", "invoke", "generate", "run", "create"):
            method = getattr(self.llm_client, method_name, None)
            if callable(method):
                return method(
                    messages=[
                        {
                            "role": "system",
                            "content": "Return a JSON object with decision_summary, action, args, termination, termination_reason.",
                        },
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                    response_format={"type": "json_object"},
                )
        raise AttributeError("llm_client_has_no_supported_completion_method")

    def _extract_content(self, response: Any) -> str | None:
        if isinstance(getattr(response, "content", None), str):
            return response.content
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        message = getattr(response, "message", None)
        if isinstance(getattr(message, "content", None), str):
            return message.content
        choices = getattr(response, "choices", None)
        if isinstance(choices, list) and choices:
            message = getattr(choices[0], "message", None)
            if isinstance(getattr(message, "content", None), str):
                return message.content
        return None

    def _usage_metrics(self, response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        return {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }

    def _build_llm_input(
        self,
        *,
        asset: str,
        round_number: int,
        allowed_specs: list[ToolSpec],
        context: dict[str, Any],
        observations: list[dict[str, Any]],
        tool_results: list[ToolResult],
    ) -> dict[str, Any]:
        return {
            "asset": asset,
            "round": round_number,
            "allowed_tools": [
                {
                    "name": spec.get("name"),
                    "domain": spec.get("domain"),
                    "description": spec.get("description"),
                    "input_schema": spec.get("input_schema"),
                }
                for spec in allowed_specs
            ],
            "context": {
                "horizon": context.get("horizon"),
                "focus": context.get("focus"),
                "market_context": context.get("market_context"),
                "protocol_context": context.get("protocol_context"),
                "asset_memory": context.get("asset_memory"),
                "timeframes": context.get("timeframes"),
                "market_type": context.get("market_type"),
            },
            "observations": observations,
            "tool_results": [
                {
                    "tool_name": result.get("tool_name"),
                    "status": result.get("status"),
                    "output_summary": result.get("output_summary"),
                    "reason": result.get("reason"),
                }
                for result in tool_results
            ],
        }

    def _validate_args(self, spec: ToolSpec, args: dict[str, Any]) -> bool:
        schema = spec.get("input_schema") or {}
        if schema.get("type") != "object":
            return isinstance(args, dict)
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        for field in required:
            if field not in args:
                return False
        for key, value in args.items():
            prop = properties.get(key)
            if not isinstance(prop, dict):
                return False
            expected_type = prop.get("type")
            if expected_type == "string" and not isinstance(value, str):
                return False
            if expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
                return False
            if expected_type == "number" and not isinstance(value, (int, float)):
                return False
            if expected_type == "boolean" and not isinstance(value, bool):
                return False
            if expected_type == "object" and not isinstance(value, dict):
                return False
            if expected_type == "array" and not isinstance(value, list):
                return False
        return True

    def _call_signature(self, tool_name: str, args: dict[str, Any]) -> str:
        return f"{tool_name}:{json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"

    def _execute_tool(
        self,
        *,
        trace_id: str,
        llm_span_id: str,
        tool_name: str,
        args: dict[str, Any],
        spec: ToolSpec | None,
    ) -> tuple[ToolResult | None, dict[str, Any] | None, bool]:
        if spec is None:
            return None, None, False

        tool_span = self.trace_runtime.start_span(
            trace_id=trace_id,
            parent_span_id=llm_span_id,
            kind="tool",
            name=tool_name,
            input_summary=args,
            attributes={
                "agent": self.agent_name,
                "tool_name": tool_name,
                "tool_server": spec.get("server"),
                "tool_domain": spec.get("domain"),
                "args": args,
                "retry_count": 0,
                "degraded": False,
            },
        )
        result = self.tool_runtime.execute(
            tool_name=tool_name,
            args=args,
            trace_context={"trace_id": trace_id, "agent": self.agent_name},
        )
        self.trace_runtime.finish_span(
            span_id=tool_span["span_id"],
            status=result["status"],
            output_summary=result["output_summary"],
            metrics=result["metrics"],
            audit={"actor": self.agent_name, "audit_level": spec.get("audit_level"), "replay_mode": spec.get("replay_mode")},
            attributes={
                "result_preview": result["output_summary"],
                "degraded": result["degraded"],
                "reason": result.get("reason"),
            },
            error=result.get("error"),
        )

        if result["status"] == "failed":
            return result, None, False

        observation = self._observation_from_result(result)
        return result, observation, observation is not None and observation.get("status") == "success"

    def _observation_from_result(self, result: ToolResult) -> dict[str, Any] | None:
        if callable(self.observation_builder):
            custom = self.observation_builder(result)
            if custom is not None:
                return custom
        output = result["output"]
        tool_name = result["tool_name"]
        summary = ""
        structured_data: dict[str, Any] = {}

        if tool_name == "search_web":
            results = output.get("results") or []
            search_text = " ".join(
                " ".join(
                    str(part or "")
                    for part in (item.get("title"), item.get("snippet"), item.get("highlights"))
                )
                for item in results
                if isinstance(item, dict)
            )
            summary = f"Found {len(results)} web sources for follow-up."
            structured_data = {
                "findings": [item.get("title") for item in results if isinstance(item, dict) and item.get("title")],
                "candidate_urls": [item.get("url") for item in results if isinstance(item, dict) and item.get("url")],
                "source_urls": [item.get("url") for item in results if isinstance(item, dict) and item.get("url")],
                "risks": self._extract_keywords(
                    search_text,
                    [
                        "risk",
                        "unlock",
                        "competition",
                        "regulatory",
                        "security",
                        "volatility",
                        "iran",
                        "war",
                        "oil",
                        "inflation",
                        "yield",
                        "hawkish",
                        "fed",
                        "geopolitical",
                    ],
                ),
                "catalysts": self._extract_keywords(
                    search_text,
                    [
                        "catalyst",
                        "roadmap",
                        "launch",
                        "upgrade",
                        "growth",
                        "adoption",
                        "etf",
                        "inflow",
                        "ceasefire",
                        "dovish",
                        "rate cut",
                        "liquidity",
                    ],
                ),
            }
        elif tool_name == "fetch_page":
            text = str(output.get("text") or "")
            title = str(output.get("title") or output.get("url") or "source")
            summary = f"{title} discusses research evidence for {output.get('url') or 'the asset'}."
            structured_data = {
                "findings": [title]
                + self._extract_sentences(
                    text,
                    [
                        "tokenomics",
                        "catalyst",
                        "risk",
                        "roadmap",
                        "ecosystem",
                        "fed",
                        "federal reserve",
                        "iran",
                        "war",
                        "oil",
                        "yield",
                        "inflation",
                        "geopolitical",
                        "etf",
                        "macro",
                    ],
                ),
                "risks": self._extract_keywords(
                    text,
                    [
                        "risk",
                        "unlock",
                        "competition",
                        "regulatory",
                        "security",
                        "execution",
                        "iran",
                        "war",
                        "oil",
                        "inflation",
                        "yield",
                        "hawkish",
                        "fed",
                        "geopolitical",
                    ],
                ),
                "catalysts": self._extract_keywords(
                    text,
                    [
                        "catalyst",
                        "roadmap",
                        "growth",
                        "adoption",
                        "launch",
                        "upgrade",
                        "ecosystem",
                        "etf",
                        "inflow",
                        "ceasefire",
                        "dovish",
                        "rate cut",
                        "liquidity",
                    ],
                ),
                "source_urls": [output.get("url")] if output.get("url") else [],
            }
        elif tool_name == "read_asset_memory":
            metadata = output.get("metadata") or {}
            content = str(output.get("content") or "")
            summary = f"Loaded stored memory for {output.get('asset') or 'asset'}."
            structured_data = {
                "findings": [str(metadata.get("summary"))] if metadata.get("summary") else self._extract_sentences(content, []),
                "risks": [item for item in metadata.get("risks", []) if isinstance(item, str)],
                "catalysts": [item for item in metadata.get("catalysts", []) if isinstance(item, str)],
                "source_urls": [],
            }
        elif tool_name == "get_market_snapshot":
            summary = f"Loaded market snapshot for {output.get('symbol') or 'asset'}."
            structured_data = {
                "market_fields": sorted(output.keys()),
                "findings": [f"market_cap={output['market_cap']}" for field in ("market_cap",) if output.get(field) is not None],
                "risks": [],
                "catalysts": [],
                "source_urls": [],
            }
        elif tool_name == "get_protocol_snapshot":
            summary = f"Loaded protocol snapshot for {output.get('symbol') or output.get('name') or 'asset'}."
            structured_data = {
                "protocol_fields": sorted(output.keys()),
                "findings": [f"tvl={output['tvl']}" for field in ("tvl",) if output.get(field) is not None],
                "risks": [],
                "catalysts": [],
                "source_urls": [],
            }
        elif tool_name == "get_ticker":
            summary = f"Loaded ticker anchor for {output.get('symbol') or 'asset'}."
            structured_data = {
                "market_fields": sorted(output.keys()),
                "findings": [f"last_price={output['last_price']}" for field in ("last_price",) if output.get(field) is not None],
                "risks": [],
                "catalysts": [],
                "source_urls": [],
            }
        elif tool_name == "get_klines":
            summary = f"Loaded {len(output.get('candles') or [])} candles for {output.get('symbol') or 'asset'}."
            structured_data = {
                "market_fields": sorted(output.keys()),
                "findings": [f"candles={len(output.get('candles') or [])}"],
                "risks": [],
                "catalysts": [],
                "source_urls": [],
            }

        if not summary and not structured_data:
            return None
        return {
            "tool_name": tool_name,
            "status": result["status"],
            "summary": summary,
            "structured_data": structured_data,
            "output_summary": result["output_summary"],
            "error": result.get("error"),
        }

    def _derive_missing_information(self, *, context: dict[str, Any], observations: list[dict[str, Any]]) -> list[str]:
        if callable(self.missing_information_builder):
            return list(self.missing_information_builder(context=context, observations=observations))
        findings = self._collect_strings(observations, "findings")
        risks = self._collect_strings(observations, "risks")
        catalysts = self._collect_strings(observations, "catalysts")
        has_market_observation = any(
            observation.get("status") == "success"
            and observation.get("tool_name") in {"get_market_snapshot", "get_protocol_snapshot", "get_ticker", "get_klines"}
            for observation in observations
        )
        source_urls = {
            url
            for observation in observations
            for url in ((observation.get("structured_data") or {}).get("source_urls") or [])
            if isinstance(url, str) and url
        }

        missing: list[str] = []
        if not findings:
            missing.append("Factual findings remain thin.")
        if not risks:
            missing.append("Risk evidence is thin.")
        if not catalysts:
            missing.append("Catalyst evidence is thin.")
        if not has_market_observation:
            missing.append("Market-side evidence is missing.")
        if not source_urls and not any(observation.get("tool_name") == "search_web" for observation in observations):
            missing.append("Source coverage is missing.")
        return missing

    def _is_evidence_sufficient(self, *, context: dict[str, Any], observations: list[dict[str, Any]]) -> bool:
        if callable(self.evidence_sufficiency_checker):
            return bool(self.evidence_sufficiency_checker(context=context, observations=observations))
        missing = self._derive_missing_information(context=context, observations=observations)
        has_market_side = any(
            observation.get("status") == "success"
            and observation.get("tool_name") in {"get_market_snapshot", "get_protocol_snapshot", "get_ticker", "get_klines"}
            for observation in observations
        )
        has_research_side = any(
            observation.get("status") == "success"
            and observation.get("tool_name") in {"fetch_page", "read_asset_memory"}
            and bool(observation.get("summary"))
            for observation in observations
        )
        return has_market_side and has_research_side and len(missing) <= 2

    def _build_agent_loop_entry(
        self,
        *,
        round_number: int,
        decision_summary: str,
        action: str | None,
        args: dict[str, Any],
        tool_result: ToolResult | None,
        termination_reason: str | None = None,
        degraded_reason: str | None = None,
        missing_information: list[str] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "round": round_number,
            "decision": {"summary": decision_summary},
            "action": {"tool": action, "input": args},
        }
        if tool_result is not None:
            entry["result"] = {
                "status": tool_result["status"],
                "tool_name": tool_result["tool_name"],
                "output_summary": tool_result["output_summary"],
                "reason": tool_result.get("reason"),
            }
        if missing_information is not None:
            entry["observation"] = {"missing_information": missing_information}
        if degraded_reason:
            entry["degraded_reason"] = degraded_reason
        if termination_reason:
            entry["termination"] = {"reason": termination_reason}
        return entry

    def _collect_strings(self, observations: list[dict[str, Any]], key: str) -> list[str]:
        items: list[str] = []
        for observation in observations:
            if observation.get("status") != "success":
                continue
            structured_data = observation.get("structured_data") or {}
            values = structured_data.get(key) or []
            for value in values:
                if isinstance(value, str) and value.strip():
                    items.append(value.strip())
        return list(dict.fromkeys(items))

    def _evidence_markers(self, observations: list[dict[str, Any]]) -> set[str]:
        markers: set[str] = set()
        for observation in observations:
            if observation.get("status") != "success":
                continue
            tool_name = str(observation.get("tool_name") or "")
            summary = str(observation.get("summary") or "").strip()
            if tool_name and summary:
                markers.add(f"summary:{tool_name}:{summary}")
            structured_data = observation.get("structured_data") or {}
            for key, values in structured_data.items():
                if isinstance(values, list):
                    for value in values:
                        if isinstance(value, str) and value.strip():
                            markers.add(f"structured:{tool_name}:{key}:{value.strip()}")
                        elif isinstance(value, (int, float)):
                            markers.add(f"structured:{tool_name}:{key}:{value}")
                elif isinstance(values, str) and values.strip():
                    markers.add(f"structured:{tool_name}:{key}:{values.strip()}")
            output_summary = observation.get("output_summary") or {}
            for key in ("url", "source", "symbol", "timeframe"):
                value = output_summary.get(key)
                if isinstance(value, str) and value.strip():
                    markers.add(f"output:{tool_name}:{key}:{value.strip()}")
        return markers

    def _has_new_evidence(
        self,
        evidence_before: set[str],
        observations: list[dict[str, Any]],
        observation: dict[str, Any] | None,
        made_progress: bool,
    ) -> bool:
        if observation is None or not made_progress or observation.get("status") != "success":
            return False
        return bool(self._evidence_markers(observations) - evidence_before)

    def _resolve_model_name(self, response: Any) -> str | None:
        for value in (getattr(response, "model", None), getattr(self.llm_client, "model", None)):
            if isinstance(value, str) and value.strip():
                return value
        return None

    def _resolve_provider_name(self, response: Any) -> str | None:
        for value in (getattr(response, "provider", None), getattr(self.llm_client, "provider", None)):
            if isinstance(value, str) and value.strip():
                return value
        return self.llm_client.__class__.__name__

    def _resolve_temperature(self, response: Any) -> float | int | None:
        for value in (getattr(response, "temperature", None), getattr(self.llm_client, "temperature", None)):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
        return None

    def _resolve_fallback_error(self, response: Any) -> str | None:
        value = getattr(response, "fallback_error", None)
        if isinstance(value, str) and value.strip():
            return value
        return None

    def _extract_keywords(self, text: str, keywords: list[str]) -> list[str]:
        lowered = text.lower()
        matches = [keyword for keyword in keywords if keyword in lowered]
        return list(dict.fromkeys(matches))

    def _extract_sentences(self, text: str, keywords: list[str]) -> list[str]:
        if not text.strip():
            return []
        sentences = [segment.strip() for segment in text.replace("\n", " ").split(".") if segment.strip()]
        if not keywords:
            return sentences[:2]
        matched = [sentence for sentence in sentences if any(keyword in sentence.lower() for keyword in keywords)]
        return matched[:3]
