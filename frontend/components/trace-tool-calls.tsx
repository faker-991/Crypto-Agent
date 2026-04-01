type TraceToolCallsProps = {
  taskResults?: Array<Record<string, unknown>> | null;
};

type NormalizedToolCall = {
  agent: string;
  taskType: string;
  tool: string;
  status: string;
  round?: number | null;
  timeframe?: string | null;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  error?: string | null;
};

export function TraceToolCalls({ taskResults }: TraceToolCallsProps) {
  const calls = flattenToolCalls(taskResults);
  if (!calls.length) {
    return null;
  }

  const searchCalls = calls.filter((call) => call.tool === "search_web");

  return (
    <section className="rounded-[1.6rem] border border-black/10 bg-white/75 p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-black/45">Tool Calls</p>
          <h3 className="mt-2 text-2xl font-semibold text-black">工具调用与 WebSearch 结果</h3>
        </div>
        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-black/55">
          {calls.length} 次调用
        </span>
      </div>

      {searchCalls.length ? (
        <div className="mt-5 rounded-[1.25rem] border border-sky-200 bg-sky-50/70 p-4">
          <p className="text-[11px] uppercase tracking-[0.2em] text-sky-900/55">WebSearch</p>
          <div className="mt-3 space-y-4">
            {searchCalls.map((call, index) => {
              const results = resolveSearchResults(call);
              const query = resolveSearchQuery(call);
              const provider = resolveSearchProvider(call);
              return (
                <div key={`search-${index}`} className="rounded-[1rem] border border-sky-200/70 bg-white/80 p-3">
                  <div className="flex flex-wrap gap-2">
                    <MiniPill label={call.agent} />
                    <MiniPill label={`status ${localizeStatus(call.status)}`} />
                    {call.round ? <MiniPill label={`round ${call.round}`} /> : null}
                    {provider ? <MiniPill label={`provider ${provider}`} /> : null}
                    <MiniPill label={`results ${results.length || numberValue(call.output.result_count) || 0}`} />
                  </div>
                  <p className="mt-3 text-sm leading-7 text-black/78">
                    <span className="font-semibold text-black">query:</span> {query || "无"}
                  </p>
                  {results.length ? (
                    <ul className="mt-3 space-y-2 text-sm leading-7 text-black/72">
                      {results.slice(0, 5).map((item, itemIndex) => {
                        const record = asRecord(item);
                        return (
                          <li key={`result-${itemIndex}`} className="rounded-[0.95rem] border border-black/10 bg-white px-3 py-3">
                            <p className="font-semibold text-black/82">{stringValue(record.title) || stringValue(record.url) || "result"}</p>
                            {stringValue(record.url) ? <p className="mt-1 text-xs text-black/52">{record.url as string}</p> : null}
                            {stringValue(record.snippet) ? <p className="mt-2 text-sm leading-6 text-black/68">{record.snippet as string}</p> : null}
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="mt-3 text-sm text-amber-800/80">这次搜索没有返回可用网页结果。</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        {calls.map((call, index) => (
          <article key={`${call.tool}-${index}`} className="rounded-[1.2rem] border border-black/10 bg-[#f8f3eb] p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.2em] text-black/42">{call.taskType}</p>
                <h4 className="mt-2 text-base font-semibold text-black/82">{call.tool}</h4>
              </div>
              <span className={`rounded-full px-3 py-1 text-[11px] uppercase tracking-[0.18em] ${statusClass(call.status)}`}>
                {localizeStatus(call.status)}
              </span>
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <MiniPill label={call.agent} />
              {call.round ? <MiniPill label={`round ${call.round}`} /> : null}
              {call.timeframe ? <MiniPill label={call.timeframe} /> : null}
            </div>

            <div className="mt-4 space-y-3 text-sm leading-7 text-black/74">
              <div>
                <p className="text-[11px] uppercase tracking-[0.2em] text-black/42">Input</p>
                <p className="mt-1 break-all">{compactObject(call.input)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.2em] text-black/42">Output</p>
                <p className="mt-1 break-all">{summarizeOutput(call.tool, call.output)}</p>
              </div>
              {call.error ? (
                <div className="rounded-[0.95rem] border border-rose-200 bg-rose-50/70 px-3 py-2 text-rose-800/82">
                  {call.error}
                </div>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function flattenToolCalls(taskResults?: Array<Record<string, unknown>> | null): NormalizedToolCall[] {
  const items: NormalizedToolCall[] = [];
  for (const task of taskResults ?? []) {
    const payload = asRecord(task.payload);
    const toolCalls = asList(task.tool_calls).length ? asList(task.tool_calls) : asList(payload.tool_calls);
    for (const raw of toolCalls) {
      const call = asRecord(raw);
      const output = asRecord(call.output_summary).length ? asRecord(call.output_summary) : asRecord(call.output);
      items.push({
        agent: stringValue(task.agent) || "unknown",
        taskType: stringValue(task.task_type) || "task",
        tool: stringValue(call.tool_name) || stringValue(call.tool) || "unknown_tool",
        status:
          stringValue(call.status) ||
          (stringValue(call.error) ? "failed" : stringValue(output.degraded_reason) ? "degraded" : "success"),
        round: numberValue(call.round),
        timeframe: stringValue(call.timeframe) || stringValue(output.timeframe) || stringValue(asRecord(call.input).timeframe),
        input: asRecord(call.args).length ? asRecord(call.args) : asRecord(call.input),
        output,
        error: stringValue(call.error),
      });
    }
  }
  return items;
}

function summarizeOutput(tool: string, output: Record<string, unknown>) {
  if (tool === "search_web") {
    const provider = stringValue(output.provider) || "unknown";
    const results = asList(output.results);
    const count = results.length || numberValue(output.result_count) || 0;
    return `provider=${provider}; results=${count}`;
  }
  if (tool === "fetch_page") {
    return [stringValue(output.title), stringValue(output.url), stringValue(output.strategy), stringValue(output.failure_reason)]
      .filter(Boolean)
      .join(" · ") || compactObject(output);
  }
  if (tool === "get_klines") {
    return [stringValue(output.source), stringValue(output.market_type), stringValue(output.timeframe)]
      .filter(Boolean)
      .join(" · ") || compactObject(output);
  }
  return compactObject(output);
}

function resolveSearchQuery(call: NormalizedToolCall) {
  return (
    stringValue(call.input.query) ||
    stringValue(call.output.query) ||
    stringValue(asRecord(call.output.output_summary).query) ||
    stringValue(asRecord(call.output.output).query)
  );
}

function resolveSearchProvider(call: NormalizedToolCall) {
  return (
    stringValue(call.output.provider) ||
    stringValue(asRecord(call.output.output_summary).provider) ||
    stringValue(asRecord(call.output.output).provider)
  );
}

function resolveSearchResults(call: NormalizedToolCall) {
  const direct = asList(call.output.results);
  if (direct.length) {
    return direct;
  }
  const summaryResults = asList(asRecord(call.output.output_summary).results);
  if (summaryResults.length) {
    return summaryResults;
  }
  return asList(asRecord(call.output.output).results);
}

function compactObject(value: Record<string, unknown>) {
  try {
    return JSON.stringify(value, null, 0);
  } catch {
    return String(value);
  }
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

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
