import { fetchMcpServers, fetchTraceSummaries, fetchTrace, type McpServer } from "../../lib/api";

export default async function ToolsPage() {
  const [mcpData, traceIndex] = await Promise.all([
    fetchMcpServers(),
    fetchTraceSummaries(),
  ]);

  const recentTraces = traceIndex.items.slice(0, 20);
  const recentCalls: {
    ts: string;
    server: string;
    tool: string;
    input: Record<string, unknown>;
    durationMs?: number;
    status: string;
  }[] = [];

  for (const summary of recentTraces) {
    try {
      const trace = await fetchTrace(summary.id);
      for (const taskResult of trace.task_results ?? []) {
        const toolCalls = (taskResult.tool_calls ?? []) as Array<Record<string, unknown>>;
        for (const call of toolCalls) {
          const normalized = normalizeRecentCall(summary.timestamp, taskResult, call);
          if (!normalized) continue;
          recentCalls.push(normalized);
        }
      }
    } catch {
      // skip unreadable traces
    }
  }

  return (
    <main className="grid gap-6 xl:grid-cols-[1fr_1fr]">
      {/* Left: MCP Server Registry */}
      <section className="rounded-[2rem] border border-black/10 bg-white/75 p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-black/45">MCP 工具注册表</p>
        <h2 className="mt-2 text-3xl font-semibold">Tool Registry</h2>
        <p className="mt-3 text-sm leading-7 text-black/65">
          以 MCP Server 形式封装的工具，可独立运行并被任意 MCP 兼容 Host 接入。
        </p>

        <div className="mt-6 space-y-5">
          {mcpData.servers.length === 0 ? (
            <p className="text-sm text-black/45">暂无注册的 MCP Server。</p>
          ) : (
            mcpData.servers.map((server) => <ServerCard key={server.name} server={server} />)
          )}
        </div>
      </section>

      {/* Right: Recent MCP Tool Calls */}
      <section className="rounded-[2rem] border border-black/10 bg-white/75 p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-black/45">最近调用记录</p>
        <h2 className="mt-2 text-3xl font-semibold">Tool Calls</h2>
        <p className="mt-3 text-sm leading-7 text-black/65">
          从最近 Trace 中提取的 MCP 工具调用记录，包含调用耗时与状态。
        </p>

        <div className="mt-6 space-y-3">
          {recentCalls.length === 0 ? (
            <p className="text-sm text-black/45">暂无 MCP 工具调用记录。发起一次查询后此处会出现数据。</p>
          ) : (
            recentCalls.slice(0, 30).map((call, index) => (
              <div
                key={index}
                className="rounded-[1.5rem] border border-black/10 bg-sand/70 px-4 py-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-black/45">
                      {formatTimestamp(call.ts)}
                    </p>
                    <p className="mt-1 truncate text-sm font-semibold">
                      {call.server} / {call.tool}
                    </p>
                    <p className="mt-1 truncate text-xs text-black/55">
                      {formatInput(call.input)}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] uppercase tracking-[0.18em] ${
                        call.status === "success"
                          ? "bg-green-50 text-green-700"
                          : call.status === "insufficient"
                          ? "bg-amber-50 text-amber-700"
                          : "bg-red-50 text-red-700"
                      }`}
                    >
                      {call.status}
                    </span>
                    {call.durationMs != null && (
                      <span className="text-[11px] text-black/40">
                        {call.durationMs < 1000
                          ? `${call.durationMs.toFixed(0)} ms`
                          : `${(call.durationMs / 1000).toFixed(1)} s`}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

function ServerCard({ server }: { server: McpServer }) {
  return (
    <div className="rounded-[1.5rem] border border-black/10 bg-sand/50 px-5 py-4">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-green-400" />
        <p className="text-sm font-semibold">{server.name}</p>
      </div>
      <p className="mt-1 text-xs text-black/55">{server.description}</p>
      <div className="mt-3 space-y-2">
        {server.tools.map((tool) => (
          <div key={tool.name} className="rounded-xl bg-white/60 px-3 py-2">
            <p className="text-xs font-semibold text-black/80">{tool.name}</p>
            <p className="mt-0.5 text-[11px] leading-5 text-black/50">{tool.description}</p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {Object.entries(tool.inputSchema.properties ?? {}).map(([key, schema]) => (
                <span
                  key={key}
                  className="rounded-full bg-black/5 px-2 py-0.5 text-[10px] text-black/60"
                >
                  {key}: {schema.type}
                  {tool.inputSchema.required?.includes(key) ? "" : "?"}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatTimestamp(ts: string): string {
  if (!ts) return "";
  try {
    const cleaned = ts.replace(/(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2}).*/, "$1-$2-$3T$4:$5:$6Z");
    const d = new Date(cleaned.includes("T") && cleaned.includes("-") ? cleaned : ts);
    if (isNaN(d.getTime())) return ts.slice(0, 16);
    return d.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts.slice(0, 16);
  }
}

function formatInput(input: Record<string, unknown>): string {
  const parts = Object.entries(input)
    .slice(0, 3)
    .map(([k, v]) => `${k}=${String(v).slice(0, 20)}`);
  return parts.join("  ·  ") || "—";
}

function normalizeRecentCall(
  timestamp: string,
  taskResult: Record<string, unknown>,
  call: Record<string, unknown>,
):
  | {
      ts: string;
      server: string;
      tool: string;
      input: Record<string, unknown>;
      durationMs?: number;
      status: string;
    }
  | null {
  const server =
    typeof call.mcp_server === "string"
      ? call.mcp_server
      : typeof call.server === "string"
        ? call.server
        : typeof call.domain === "string"
          ? call.domain
          : null;
  const tool =
    typeof call.tool === "string"
      ? call.tool
      : typeof call.tool_name === "string"
        ? call.tool_name
        : null;
  const input =
    call.input && typeof call.input === "object" && !Array.isArray(call.input)
      ? (call.input as Record<string, unknown>)
      : call.args && typeof call.args === "object" && !Array.isArray(call.args)
        ? (call.args as Record<string, unknown>)
        : {};
  const status =
    typeof call.status === "string"
      ? call.status
      : typeof taskResult.status === "string"
        ? taskResult.status
        : "unknown";

  if (!server || !tool) {
    return null;
  }

  return {
    ts: timestamp,
    server,
    tool,
    input,
    durationMs: call.duration_ms != null ? Number(call.duration_ms) : undefined,
    status,
  };
}
