"use client";

import type { ReactNode } from "react";
import Link from "next/link";

import type { ConversationTranscript } from "../lib/api";

type ConversationPanelProps = {
  transcript: ConversationTranscript | null;
  isPending: boolean;
  input: string;
  onInputChange: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
};

export function ConversationPanel({
  transcript,
  isPending,
  input,
  onInputChange,
  onSubmit,
}: ConversationPanelProps) {
  return (
    <div className="flex min-h-[72vh] flex-col overflow-hidden rounded-[2rem] border border-black/10 bg-[linear-gradient(180deg,rgba(19,19,16,0.96),rgba(44,35,27,0.96))] text-white">
      <div className="border-b border-white/10 px-5 py-4 sm:px-6">
        <p className="text-xs uppercase tracking-[0.24em] text-white/45">当前会话</p>
        <h3 className="mt-2 text-2xl font-semibold">{transcript?.title ?? "请选择或新建一个会话"}</h3>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5 sm:px-6">
        {transcript?.messages?.length ? (
          transcript.messages.map((message) => <ChatBubble key={message.id} message={message} />)
        ) : (
          <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
            <p className="text-xs uppercase tracking-[0.24em] text-white/45">已就绪</p>
            <p className="mt-3 max-w-xl text-sm leading-7 text-white/74">
              可以直接问价格、K 线、合约走势等问题。每个会话都会保留历史回复，并且可以继续追踪执行过程。
            </p>
          </div>
        )}
      </div>
      <form className="border-t border-white/10 bg-black/10 px-5 py-4 sm:px-6" onSubmit={onSubmit}>
        <textarea
          className="min-h-36 w-full rounded-[1.75rem] border border-[#6f5a45] bg-[#16110d] px-4 py-4 text-sm text-[#fff6ea] caret-[#f3c15e] outline-none transition focus:border-[#f3c15e] focus:ring-2 focus:ring-[#f3c15e]/30 placeholder:text-[#c7b9a8]"
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="输入你想看的现货、合约、价格走势或 K 线问题。"
          value={input}
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs uppercase tracking-[0.18em] text-white/42">
            多轮上下文会保留在左侧边栏里；点击“查看轨迹”可以进入完整执行过程。
          </p>
          <button
            className="rounded-full bg-amber-300 px-5 py-2.5 text-sm font-semibold text-black disabled:opacity-55"
            disabled={isPending || !transcript}
            type="submit"
          >
            {isPending ? "执行中..." : "发送"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ChatBubble({ message }: { message: ConversationTranscript["messages"][number] }) {
  const isUser = message.role === "user";
  const execution = message.execution_summary;
  const highlights = summarizeHighlights(execution);
  const traceId = message.trace_id || null;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[88%] rounded-[1.75rem] px-4 py-4 shadow-sm ${
          isUser
            ? "bg-[linear-gradient(145deg,rgba(243,193,94,0.96),rgba(236,165,84,0.98))] text-black"
            : "border border-white/10 bg-white/7 text-white"
        }`}
      >
        <p className={`text-[11px] uppercase tracking-[0.24em] ${isUser ? "text-black/48" : "text-white/42"}`}>
          {isUser ? "用户" : "助手"}
        </p>
        {isUser ? (
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-black/78">{message.content}</p>
        ) : (
          <div className="mt-3">{renderAssistantMessage(message.content)}</div>
        )}

        {!isUser ? (
          <div className="mt-4 space-y-4">
            {message.answer_generation ? (
              <div className="rounded-[1.25rem] border border-white/10 bg-black/10 p-4">
                <p className="text-[11px] uppercase tracking-[0.22em] text-white/45">回答生成</p>
                <p className="mt-2 text-sm leading-7 text-white/78">
                  {message.answer_generation.status === "ready"
                    ? `LLM 回答已生成${message.answer_generation.model ? `（${message.answer_generation.model}）` : ""}。`
                    : message.answer_generation.status === "unavailable"
                      ? `LLM 当前不可用${message.answer_generation.error ? `：${message.answer_generation.error}` : "。"}`
                      : "本次未执行 LLM 生成。"}
                </p>
              </div>
            ) : null}

            {highlights.length ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {highlights.map((item) => (
                  <div key={`${item.label}-${item.value}`} className="rounded-[1.15rem] border border-white/10 bg-white/6 p-3">
                    <p className="text-[11px] uppercase tracking-[0.2em] text-white/42">{item.label}</p>
                    <p className="mt-2 text-sm text-white/78">{item.value}</p>
                  </div>
                ))}
              </div>
            ) : null}

            {traceId ? (
              <Link
                className="inline-flex rounded-full border border-white/10 bg-white/8 px-4 py-2 text-xs uppercase tracking-[0.2em] text-white/72 transition hover:bg-white/14"
                href={`/traces?trace=${traceId}`}
                scroll
              >
                查看轨迹
              </Link>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function summarizeHighlights(execution: Record<string, unknown> | null | undefined): Array<{ label: string; value: string }> {
  if (!execution) {
    return [];
  }

  const items: Array<{ label: string; value: string }> = [];
  if (typeof execution.asset === "string") {
    items.push({ label: "标的", value: execution.asset });
  }

  if (typeof execution.decision_mode === "string") {
    items.push({ label: "模式", value: execution.decision_mode });
  }

  const marketSummary = execution.market_summary;
  if (marketSummary && typeof marketSummary === "object") {
    const summary = marketSummary as Record<string, unknown>;
    if (typeof summary.market_type === "string") {
      items.push({ label: "市场", value: summary.market_type });
    }
    if (Array.isArray(summary.timeframes) && summary.timeframes.length) {
      items.push({ label: "周期", value: summary.timeframes.join(", ") });
    }
  }

  const agentSufficiency = execution.agent_sufficiency;
  if (agentSufficiency && typeof agentSufficiency === "object") {
    const states = Object.entries(agentSufficiency as Record<string, unknown>)
      .map(([agent, value]) => `${agent}: ${value ? "充足" : "不足"}`)
      .join(" | ");
    if (states) {
      items.push({ label: "证据", value: states });
    }
  }

  return items.slice(0, 4);
}

function renderAssistantMessage(content: string): ReactNode {
  const blocks = splitMessageBlocks(content);

  return (
    <div className="space-y-4 text-sm leading-7 text-white/82">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return (
            <div key={`heading-${index}`} className="space-y-2">
              <p className="text-[11px] uppercase tracking-[0.24em] text-amber-200/70">{block.levelLabel}</p>
              <h4 className="text-base font-semibold text-white">{renderInline(block.text)}</h4>
            </div>
          );
        }
        if (block.type === "list") {
          return (
            <ul key={`list-${index}`} className="space-y-2 rounded-[1.1rem] border border-white/8 bg-black/10 px-4 py-3">
              {block.items.map((item, itemIndex) => (
                <li key={`item-${itemIndex}`} className="flex gap-3 text-white/80">
                  <span className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-amber-200/80" />
                  <span>{renderInline(item)}</span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={`paragraph-${index}`} className="whitespace-pre-wrap text-white/82">
            {renderInline(block.text)}
          </p>
        );
      })}
    </div>
  );
}

function splitMessageBlocks(content: string): Array<
  | { type: "heading"; text: string; levelLabel: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] }
> {
  const normalized = content.replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return [{ type: "paragraph", text: "" }];
  }

  const lines = normalized.split("\n");
  const blocks: Array<
    | { type: "heading"; text: string; levelLabel: string }
    | { type: "paragraph"; text: string }
    | { type: "list"; items: string[] }
  > = [];

  let paragraphBuffer: string[] = [];
  let listBuffer: string[] = [];

  const flushParagraph = () => {
    if (!paragraphBuffer.length) {
      return;
    }
    blocks.push({ type: "paragraph", text: paragraphBuffer.join("\n").trim() });
    paragraphBuffer = [];
  };

  const flushList = () => {
    if (!listBuffer.length) {
      return;
    }
    blocks.push({ type: "list", items: listBuffer });
    listBuffer = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      blocks.push({
        type: "heading",
        text: headingMatch[2].trim(),
        levelLabel: `章节 ${headingMatch[1].length}`,
      });
      continue;
    }
    const listMatch = line.match(/^[-*•]\s+(.+)$/);
    if (listMatch) {
      flushParagraph();
      listBuffer.push(listMatch[1].trim());
      continue;
    }
    flushList();
    paragraphBuffer.push(line);
  }

  flushParagraph();
  flushList();
  return blocks;
}

function renderInline(text: string): ReactNode {
  const nodes: ReactNode[] = [];
  const pattern = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  match = pattern.exec(text);
  while (match) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    nodes.push(
      <strong key={`strong-${match.index}`} className="font-semibold text-white">
        {match[1]}
      </strong>,
    );
    lastIndex = match.index + match[0].length;
    match = pattern.exec(text);
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  if (!nodes.length) {
    return text;
  }

  return <>{nodes}</>;
}
