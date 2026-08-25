"use client";

import { useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api";

interface ChatImage {
  id: string;
  name: string;
  image_url: string;
}

interface ChatReply {
  text: string;
  images?: ChatImage[];
}

interface Message {
  role: "user" | "ai";
  text: string;
  images?: ChatImage[];
}

interface ChatWidgetProps {
  greeting: string;
  placeholder: string;
  onSend: (message: string, history: { role: "user" | "ai"; text: string }[]) => Promise<ChatReply>;
}

export function ChatWidget({ greeting, placeholder, onSend }: ChatWidgetProps) {
  const [messages, setMessages] = useState<Message[]>([{ role: "ai", text: greeting }]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || sending) return;

    // P1-6 - 백엔드는 세션을 두지 않으므로, 지금까지 이 위젯이 화면에
    // 들고 있던 전체 대화를 매번 그대로 실어 보낸다(이 메시지 이전까지).
    const historyBeforeThisMessage = messages.map((m) => ({ role: m.role, text: m.text }));
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setSending(true);
    try {
      const reply = await onSend(question, historyBeforeThisMessage);
      setMessages((prev) => [...prev, { role: "ai", text: reply.text, images: reply.images }]);
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
            {m.images && m.images.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {m.images.map((img) => (
                  <img
                    key={img.id}
                    src={img.image_url}
                    alt={img.name}
                    className="h-20 w-20 rounded-md border border-gray-200 object-cover"
                  />
                ))}
              </div>
            )}
          </div>
        ))}
        {sending && <p className="text-left text-sm text-gray-400">답변 작성 중...</p>}
      </div>
      <form onSubmit={onSubmit} className="flex gap-2 border-t border-gray-200 p-3">
        <input
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
          placeholder={placeholder}
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
