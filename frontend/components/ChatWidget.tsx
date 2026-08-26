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
  // P1-5 (REORG_DECISIONS.md) - 이 응답을 남긴 AiInteraction id. 있어야만
  // 👍/👎 버튼을 보여준다(피드백을 어느 대화에 붙일지 알아야 하므로).
  interactionId?: string;
}

interface Message {
  role: "user" | "ai";
  text: string;
  images?: ChatImage[];
  interactionId?: string;
  feedback?: "up" | "down";
}

interface ChatWidgetProps {
  greeting: string;
  placeholder: string;
  onSend: (message: string, history: { role: "user" | "ai"; text: string }[]) => Promise<ChatReply>;
  onFeedback?: (interactionId: string, feedback: "up" | "down") => void;
}

function AiAvatar() {
  return (
    <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-coral to-terracotta">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 21s7-7.58 7-12a7 7 0 1 0-14 0c0 4.42 7 12 7 12z" />
        <circle cx="12" cy="9" r="2.3" />
      </svg>
    </div>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

export function ChatWidget({ greeting, placeholder, onSend, onFeedback }: ChatWidgetProps) {
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
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: reply.text, images: reply.images, interactionId: reply.interactionId },
      ]);
    } catch (err) {
      const text =
        err instanceof ApiError ? err.message : "AI 응답을 받아오지 못했습니다. 잠시 후 다시 시도해 주세요.";
      setMessages((prev) => [...prev, { role: "ai", text }]);
    } finally {
      setSending(false);
    }
  };

  const onGiveFeedback = (index: number, feedback: "up" | "down") => {
    const message = messages[index];
    if (!message.interactionId) return;
    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, feedback } : m)));
    onFeedback?.(message.interactionId, feedback);
  };

  return (
    <div className="flex flex-col overflow-hidden rounded-3xl border border-coral/15 bg-paper shadow-[0_20px_48px_rgba(184,90,42,0.10)]">
      <div className="flex h-[28rem] flex-col gap-4 overflow-y-auto p-5 sm:p-6">
        {messages.map((m, i) => (
          <div key={i} className={"flex items-start gap-2.5 " + (m.role === "user" ? "justify-end" : "justify-start")}>
            {m.role === "ai" && <AiAvatar />}
            <div className="flex max-w-[80%] flex-col gap-2">
              <span
                className={
                  "inline-block whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed " +
                  (m.role === "user" ? "rounded-br-md bg-coral text-white" : "rounded-tl-md bg-sand text-ink")
                }
              >
                {m.text}
              </span>
              {m.images && m.images.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {m.images.map((img) => (
                    <img
                      key={img.id}
                      src={img.image_url}
                      alt={img.name}
                      className="h-16 w-16 rounded-lg border border-ink/10 object-cover sm:h-20 sm:w-20"
                    />
                  ))}
                </div>
              )}
              {m.role === "ai" && m.interactionId && onFeedback && (
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    aria-label="도움이 됐어요"
                    onClick={() => onGiveFeedback(i, "up")}
                    className={
                      "flex h-6 w-6 items-center justify-center rounded-full transition " +
                      (m.feedback === "up" ? "bg-sand text-coral-dark" : "bg-sand/60 text-ink-muted/50 hover:text-ink-muted")
                    }
                  >
                    <CheckIcon />
                  </button>
                  <button
                    type="button"
                    aria-label="도움이 안 됐어요"
                    onClick={() => onGiveFeedback(i, "down")}
                    className={
                      "flex h-6 w-6 items-center justify-center rounded-full transition " +
                      (m.feedback === "down" ? "bg-sand text-coral-dark" : "bg-sand/60 text-ink-muted/50 hover:text-ink-muted")
                    }
                  >
                    <XIcon />
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        {sending && <p className="text-sm text-ink-muted">답변 작성 중...</p>}
      </div>
      <form onSubmit={onSubmit} className="flex gap-2.5 border-t border-ink/10 p-3.5">
        <input
          className="flex-1 rounded-full border border-ink/10 bg-cream/50 px-4 py-2.5 text-sm text-ink placeholder:text-ink-muted/50 focus:border-coral focus:outline-none"
          placeholder={placeholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="rounded-full bg-coral px-6 py-2.5 text-sm font-medium text-white shadow-sm transition disabled:opacity-50"
        >
          전송
        </button>
      </form>
    </div>
  );
}
