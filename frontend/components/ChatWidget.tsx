"use client";

import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";

interface Message {
  role: "user" | "ai";
  text: string;
}

export function ChatWidget({ businessId }: { businessId: string }) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "ai", text: "안녕하세요! 영업시간, 메뉴, 주차, 반려동물 동반 여부 등 궁금한 걸 물어보세요." },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || sending) return;

    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setSending(true);
    try {
      const { reply } = await api.chat(businessId, question);
      setMessages((prev) => [...prev, { role: "ai", text: reply }]);
    } catch (err) {
      const text =
        err instanceof ApiError ? err.message : "AI 응답을 받아오지 못했습니다. 잠시 후 다시 시도해 주세요.";
      setMessages((prev) => [...prev, { role: "ai", text }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex h-[28rem] flex-col rounded-md border border-gray-200">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <span
              className={
                "inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm " +
                (m.role === "user" ? "bg-black text-white" : "bg-gray-100 text-gray-900")
              }
            >
              {m.text}
            </span>
          </div>
        ))}
        {sending && <p className="text-left text-sm text-gray-400">답변 작성 중...</p>}
      </div>
      <form onSubmit={onSubmit} className="flex gap-2 border-t border-gray-200 p-3">
        <input
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
          placeholder="예: 주차 가능한가요?"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="rounded-md bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          전송
        </button>
      </form>
    </div>
  );
}
