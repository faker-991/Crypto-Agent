"use client";

import { useEffect, useMemo, useState, useTransition } from "react";

import {
  createConversation,
  fetchConversation,
  listConversations,
  sendConversationMessage,
  type ConversationIndexItem,
  type ConversationTranscript,
} from "../lib/api";
import { ConversationPanel } from "./conversation-panel";
import { ConversationSidebar } from "./conversation-sidebar";

const STARTER_PROMPTS = [
  "BTC 现货现在怎么样",
  "看下 ETH futures 4h 和 1d",
  "SUI 值不值得继续观察，从走势看",
];

export function PlannerChat() {
  const [conversations, setConversations] = useState<ConversationIndexItem[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<ConversationTranscript | null>(null);
  const [input, setInput] = useState("帮我看下 BTC 现货日线和周线走势");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    startTransition(async () => {
      const listed = await listConversations();
      setConversations(listed.items);
      const first = listed.items[0]?.conversation_id;
      if (first) {
        setActiveConversationId(first);
        setTranscript(await fetchConversation(first));
      }
    });
  }, []);

  async function refreshListAndTranscript(nextConversationId?: string | null) {
    const listed = await listConversations();
    setConversations(listed.items);
    const selectedId = nextConversationId ?? activeConversationId ?? listed.items[0]?.conversation_id ?? null;
    setActiveConversationId(selectedId);
    if (selectedId) {
      setTranscript(await fetchConversation(selectedId));
    } else {
      setTranscript(null);
    }
  }

  function handleCreateConversation() {
    startTransition(async () => {
      const created = await createConversation(`会话 ${conversations.length + 1}`);
      await refreshListAndTranscript(created.conversation_id);
    });
  }

  function handleSelectConversation(conversationId: string) {
    startTransition(async () => {
      setActiveConversationId(conversationId);
      setTranscript(await fetchConversation(conversationId));
    });
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || !activeConversationId) {
      return;
    }
    setInput("");
    startTransition(async () => {
      await sendConversationMessage(activeConversationId, trimmed);
      await refreshListAndTranscript(activeConversationId);
    });
  }

  const suggestedPromptButtons = useMemo(
    () =>
      STARTER_PROMPTS.map((prompt) => (
        <button
          key={prompt}
          className="rounded-full border border-black/10 bg-white/75 px-4 py-2 text-xs uppercase tracking-[0.18em] text-black/62 transition hover:border-black/25 hover:bg-white"
          onClick={() => setInput(prompt)}
          type="button"
        >
          {prompt}
        </button>
      )),
    [],
  );

  return (
    <section className="rounded-[2.25rem] border border-black/10 bg-[linear-gradient(145deg,rgba(255,255,255,0.92),rgba(242,233,219,0.98))] p-5 shadow-[0_28px_90px_rgba(28,23,17,0.12)] sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-black/42">智能对话</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-[2.35rem]">提问、分析、追踪。</h2>
          <p className="mt-3 text-sm leading-7 text-black/66">
            历史会话保留在左侧边栏，主区域专注当前对话；更完整的执行过程可以在 Traces 里查看。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">{suggestedPromptButtons}</div>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[0.28fr_0.72fr] xl:items-stretch">
        <ConversationSidebar
          activeConversationId={activeConversationId}
          conversations={conversations}
          isPending={isPending}
          onCreateConversation={handleCreateConversation}
          onSelectConversation={handleSelectConversation}
        />

        <ConversationPanel
          input={input}
          isPending={isPending}
          onInputChange={setInput}
          onSubmit={handleSubmit}
          transcript={transcript}
        />
      </div>
    </section>
  );
}
