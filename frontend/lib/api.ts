export type WatchlistItem = {
  symbol: string;
  status: string;
  priority: number;
  last_reviewed_at: string;
};

export type Watchlist = {
  assets: WatchlistItem[];
};

export type PaperPosition = {
  symbol: string;
  market_type: string;
  quantity: number;
  average_entry_price: number;
  last_price: number;
  unrealized_pnl: number;
};

export type PaperPortfolio = {
  cash: number;
  positions: PaperPosition[];
};

export type WatchlistAddInput = {
  symbol: string;
  status: string;
  priority: number;
};

export type PaperOrderInput = {
  symbol: string;
  market_type: string;
  side: string;
  quantity: number;
  price: number;
};

export type ThesisResponse = {
  symbol: string;
  content: string;
};

export type MarketType = "spot" | "futures";

export type Candle = {
  symbol: string;
  timeframe: string;
  open_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type TimeframeAnalysis = {
  trend_regime: string;
  support_levels: number[];
  resistance_levels: number[];
  breakout_signal: boolean;
  drawdown_state: string;
  conclusion: string;
  candles: Candle[];
};

export type EndpointSummary = {
  integration: string;
  endpoint: string;
  market_type: string;
  url: string;
  method: string;
};

export type TickerSummary = {
  symbol: string;
  last_price: number | null;
  open_price: number | null;
  high_price: number | null;
  low_price: number | null;
  price_change: number | null;
  price_change_percent: number | null;
  volume: number | null;
  quote_volume: number | null;
  bid_price: number | null;
  ask_price: number | null;
};

export type AssetDiscoveryItem = {
  symbol: string;
  name: string | null;
  display_name_zh: string | null;
  rank: number | null;
  image: string | null;
  market_cap: number | null;
  current_price: number | null;
  price_change_percentage_24h: number | null;
  binance_symbol: string | null;
  is_binance_supported: boolean;
};

export type AssetChartSummary = {
  trend_regime: string;
  breakout_signal: boolean;
  drawdown_state: string;
  support_levels: number[];
  resistance_levels: number[];
  conclusion: string;
};

export type AssetLiveSnapshot = {
  symbol: string;
  binance_symbol: string | null;
  name: string | null;
  market_type: string;
  timeframe: string;
  is_supported: boolean;
  source: "binance" | "unavailable";
  candles: Candle[];
  ticker_summary: TickerSummary | null;
  endpoint_summary: EndpointSummary | null;
  degraded_reason: string | null;
  chart_summary: AssetChartSummary | null;
};

export type TimeframeMarketData = {
  market_type: string;
  source: "binance" | "unavailable";
  endpoint_summary: EndpointSummary | null;
  ticker_summary: TickerSummary | null;
  degraded_reason: string | null;
};

export type KlineResearchResponse = {
  symbol: string;
  market_type: string;
  analyses: Record<string, TimeframeAnalysis>;
  market_data: Record<string, TimeframeMarketData>;
};

export type MemorySummary = {
  content: string;
};

export type MemoryProfile = {
  profile: Record<string, unknown>;
};

export type MemoryAssetItem = {
  symbol: string;
  has_thesis: boolean;
  metadata: Record<string, unknown>;
};

export type MemoryAssetIndex = {
  items: MemoryAssetItem[];
};

export type MemoryJournalItem = {
  date: string;
  title: string;
  path: string;
};

export type MemoryJournal = {
  items: MemoryJournalItem[];
};

export type MemoryContextPreview = {
  kind: string;
  context: Record<string, unknown>;
};

export type PlannerTask = {
  task_id: string;
  task_type: string;
  title: string;
  slots: Record<string, unknown>;
  depends_on: string[];
};

export type PlannerExecutionResponse = {
  status: "execute" | "clarify" | "failed";
  plan: {
    goal: string;
    mode: "single_task" | "multi_task";
    decision_mode?: "clarify" | "research_only" | "kline_only" | "mixed_analysis" | null;
    needs_clarification: boolean;
    clarification_question?: string | null;
    reasoning_summary?: string | null;
    agents_to_invoke?: string[];
    tasks: PlannerTask[];
  } | null;
  task_results: Array<{
    task_id: string;
    task_type: string;
    agent: string;
    status: string;
    payload: Record<string, unknown>;
    summary?: string | null;
    evidence_sufficient?: boolean | null;
    missing_information?: string[];
    tool_calls?: Array<Record<string, unknown>>;
    rounds_used?: number | null;
  }>;
  final_answer?: string | null;
  execution_summary: Record<string, unknown>;
  trace_path?: string;
  events?: Array<{
    name: string;
    actor: string;
    detail: Record<string, unknown>;
  }>;
};

export type PlannerEvent = NonNullable<PlannerExecutionResponse["events"]>[number];

export type TraceSummary = {
  path: string;
  id: string;
  timestamp: string;
  user_query: string;
  status?: string | null;
  mode?: string | null;
  task_count?: number | null;
  agent?: string | null;
};

export type TracePayload = {
  timestamp: string;
  user_query: string;
  status?: string | null;
  plan?: Record<string, unknown> | null;
  legacy_route?: Record<string, unknown> | null;
  task_results?: Array<Record<string, unknown>>;
  final_answer?: string | null;
  execution_summary: Record<string, unknown> | null;
  events: PlannerEvent[];
  readable_workflow?: ReadableWorkflow | null;
};

export type ReadableWorkflowStage = {
  kind: "planner" | "research" | "kline" | "summary" | "unknown";
  title: string;
  status: "success" | "insufficient" | "failed" | "skipped" | "unknown";
  did: string[];
  actual_calls: string[];
  found: string[];
  conclusion: string[];
  meta: Record<string, unknown>;
};

export type ReadableWorkflow = {
  final_conclusion?: {
    status: "execute" | "clarify" | "failed" | "unknown";
    final_answer?: string | null;
    summary?: string | null;
    evidence_sufficient?: boolean | null;
    missing_information: string[];
    degraded_reason?: string | null;
  } | null;
  timeline: ReadableWorkflowStage[];
};

export type AnswerGenerationPayload = {
  status: "ready" | "unavailable" | "skipped";
  provider?: string | null;
  model?: string | null;
  answer_text?: string | null;
  error?: string | null;
  used_context: string[];
};

export type ConversationIndexItem = {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_user_message?: string | null;
  message_count: number;
};

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  plan_summary?: PlannerExecutionResponse["plan"] | null;
  execution_summary?: Record<string, unknown> | null;
  answer_generation?: AnswerGenerationPayload | null;
  trace_id?: string | null;
};

export type ConversationTranscript = {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
};

export type ConversationSendResponse = {
  assistant_message: ConversationMessage;
  plan?: PlannerExecutionResponse["plan"];
  execution_summary?: Record<string, unknown> | null;
  trace_path?: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function getJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) {
      return fallback;
    }
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export function fetchWatchlist(): Promise<Watchlist> {
  return getJson("/api/watchlist", { assets: [] });
}

export async function fetchTopAssets(): Promise<{ items: AssetDiscoveryItem[]; error: string | null }> {
  try {
    const response = await fetch(`${API_BASE}/api/assets/discovery/top`, { cache: "no-store" });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      return { items: [], error: payload?.detail ?? "默认前 20 资产暂不可用" };
    }
    const payload = (await response.json()) as { items: AssetDiscoveryItem[] };
    return { items: payload.items ?? [], error: null };
  } catch {
    return { items: [], error: "默认前 20 资产暂不可用" };
  }
}

export async function searchAssets(query: string): Promise<{ items: AssetDiscoveryItem[]; error: string | null }> {
  if (!query.trim()) {
    return { items: [], error: null };
  }
  try {
    const response = await fetch(`${API_BASE}/api/assets/discovery/search?q=${encodeURIComponent(query)}`, {
      cache: "no-store",
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      return { items: [], error: payload?.detail ?? "资产搜索暂不可用" };
    }
    const payload = (await response.json()) as { items: AssetDiscoveryItem[] };
    return { items: payload.items ?? [], error: null };
  } catch {
    return { items: [], error: "资产搜索暂不可用" };
  }
}

export function fetchPortfolio(): Promise<PaperPortfolio> {
  return getJson("/api/paper-trading/portfolio", { cash: 0, positions: [] });
}

export function fetchThesis(symbol: string): Promise<ThesisResponse> {
  return getJson(`/api/memory/thesis/${symbol}`, { symbol, content: "" });
}

export function fetchMemorySummary(): Promise<MemorySummary> {
  return getJson("/api/memory", { content: "" });
}

export function fetchMemoryProfile(): Promise<MemoryProfile> {
  return getJson("/api/memory/profile", { profile: {} });
}

export function fetchMemoryAssets(): Promise<MemoryAssetIndex> {
  return getJson("/api/memory/assets", { items: [] });
}

export function fetchMemoryJournal(): Promise<MemoryJournal> {
  return getJson("/api/memory/journal", { items: [] });
}

export function fetchMemoryContextPreview(): Promise<MemoryContextPreview> {
  return getJson("/api/memory/context-preview?kind=planner", {
    kind: "planner",
    context: {},
  });
}

export function fetchTraceSummaries(): Promise<{ items: TraceSummary[] }> {
  return getJson("/api/traces", { items: [] });
}

export function fetchTrace(traceId: string): Promise<TracePayload> {
  return getJson(`/api/traces/${traceId}`, {
    timestamp: "",
    user_query: "",
    execution_summary: null,
    events: [],
  }).then((payload) => {
    if (!payload || typeof payload !== "object") {
      return {
        timestamp: "",
        user_query: "",
        execution_summary: null,
        events: [],
      };
    }
    const record = payload as Record<string, unknown>;
    const legacyRoute = record.route;
    const tracePayload = {
      ...record,
      legacy_route:
        legacyRoute && typeof legacyRoute === "object" ? (legacyRoute as Record<string, unknown>) : null,
    } as TracePayload & { route?: unknown };
    delete tracePayload.route;
    return tracePayload;
  });
}

export type KlineAnalysisOptions = {
  marketType?: MarketType;
  timeframes?: string[];
};

export async function fetchKlineAnalysis(
  symbol: string,
  options: KlineAnalysisOptions = {},
): Promise<KlineResearchResponse> {
  const { marketType = "spot", timeframes = ["1d", "1w"] } = options;
  try {
    const response = await fetch(`${API_BASE}/api/research/kline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol,
        timeframes,
        market_type: marketType,
      }),
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("kline request failed");
    }
    return (await response.json()) as KlineResearchResponse;
  } catch {
    return {
      symbol,
      market_type: marketType,
      analyses: {},
      market_data: {},
    };
  }
}

export function fetchLiveAsset(
  symbol: string,
  marketType: MarketType,
  timeframe: string,
): Promise<AssetLiveSnapshot> {
  return getJson(
    `/api/assets/${encodeURIComponent(symbol)}/live?market=${marketType}&timeframe=${encodeURIComponent(timeframe)}`,
    {
      symbol,
      binance_symbol: null,
      name: null,
      market_type: marketType,
      timeframe,
      is_supported: false,
      source: "unavailable",
      candles: [],
      ticker_summary: null,
      endpoint_summary: null,
      degraded_reason: "实时资产请求失败",
      chart_summary: null,
    },
  );
}

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`request failed for ${path}`);
  }
  return (await response.json()) as T;
}

export function addWatchlistItem(input: WatchlistAddInput): Promise<Watchlist> {
  return postJson("/api/watchlist/add", input);
}

export function removeWatchlistItem(symbol: string): Promise<Watchlist> {
  return postJson("/api/watchlist/remove", { symbol });
}

export function submitPaperOrder(input: PaperOrderInput): Promise<PaperPortfolio> {
  return postJson("/api/paper-trading/order", input);
}

export function executePlannerQuery(user_query: string): Promise<PlannerExecutionResponse> {
  return postJson("/api/planner/execute", { user_query });
}

export function listConversations(): Promise<{ items: ConversationIndexItem[] }> {
  return getJson("/api/conversations", { items: [] });
}

export function createConversation(title?: string): Promise<ConversationTranscript> {
  return postJson("/api/conversations", { title });
}

export function fetchConversation(conversationId: string): Promise<ConversationTranscript> {
  return getJson(`/api/conversations/${conversationId}`, {
    conversation_id: conversationId,
    title: "Conversation",
    created_at: "",
    updated_at: "",
    messages: [],
  });
}

export function sendConversationMessage(
  conversationId: string,
  content: string,
): Promise<ConversationSendResponse> {
  return postJson(`/api/conversations/${conversationId}/messages`, { content });
}
