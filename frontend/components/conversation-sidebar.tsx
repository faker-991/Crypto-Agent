"use client";

import type { ConversationIndexItem } from "../lib/api";

type ConversationSidebarProps = {
  conversations: ConversationIndexItem[];
  activeConversationId: string | null;
  isPending: boolean;
  onCreateConversation: () => void;
  onSelectConversation: (conversationId: string) => void;
};

export function ConversationSidebar({
  conversations,
  activeConversationId,
  isPending,
  onCreateConversation,
  onSelectConversation,
}: ConversationSidebarProps) {
  return (
    <aside className="rounded-[1.75rem] border border-black/10 bg-white/75 p-4 shadow-sm sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-black/42">会话列表</p>
          <h3 className="mt-2 text-lg font-semibold sm:text-xl">历史会话</h3>
        </div>
        <button
          className="rounded-full border border-black/10 bg-black px-4 py-2 text-xs uppercase tracking-[0.18em] text-white disabled:opacity-50"
          disabled={isPending}
          onClick={onCreateConversation}
          type="button"
        >
          新建
        </button>
      </div>

      <div className="mt-4 max-h-[68vh] space-y-2 overflow-y-auto pr-1">
        {conversations.length ? (
          conversations.map((conversation) => {
            const active = conversation.conversation_id === activeConversationId;
            return (
              <button
                key={conversation.conversation_id}
                className={`block w-full rounded-[1.2rem] border px-3 py-3 text-left transition ${
                  active
                    ? "border-black/25 bg-black text-white"
                    : "border-black/10 bg-white/80 text-black/74 hover:border-black/20"
                }`}
                onClick={() => onSelectConversation(conversation.conversation_id)}
                type="button"
              >
                <p className={`text-sm font-semibold leading-6 ${active ? "text-white" : "text-black/78"}`}>
                  {conversation.title}
                </p>
                <p className={`mt-2 line-clamp-2 text-xs leading-6 ${active ? "text-white/62" : "text-black/55"}`}>
                  {conversation.last_user_message || "还没有消息。"}
                </p>
                <p className={`mt-2 text-[11px] uppercase tracking-[0.18em] ${active ? "text-white/45" : "text-black/42"}`}>
                  {conversation.message_count} 条消息
                </p>
              </button>
            );
          })
        ) : (
          <div className="rounded-[1.2rem] border border-black/10 bg-white/80 p-4 text-sm text-black/58">
            暂无历史会话。
          </div>
        )}
      </div>
    </aside>
  );
}
