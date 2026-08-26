"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatWidget } from "@/components/ChatWidget";
import { api, CATEGORY_LABELS, type BusinessCategory, type RecommendationItem } from "@/lib/api";

function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category as BusinessCategory] ?? category;
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

export default function DiscoverPage() {
  const router = useRouter();
  const [interactionId, setInteractionId] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [clickedIds, setClickedIds] = useState<Set<string>>(new Set());
  // 연타 방지 - clickedIds(state)는 리렌더를 거쳐 반영되므로 같은 틱에
  // 두 번 눌리는 경우까지는 못 막는다. ref는 즉시 반영되는 별도 방어선.
  const inFlightIds = useRef<Set<string>>(new Set());

  const handleSend = async (message: string) => {
    const response = await api.recommend(message);
    setInteractionId(response.interaction_id);
    setRecommendations(response.recommendations);
    setClickedIds(new Set());
    inFlightIds.current = new Set();
    return { text: response.reply };
  };

  const handleRecommendationClick = (item: RecommendationItem) => {
    // 클릭 tracking 실패가 있어도 이동 자체는 항상 되어야 하므로, 이동
    // 로직은 tracking 성공/실패와 무관하게 먼저 결정한다.
    if (item.source === "business") {
      router.push(`/businesses/${item.id}`);
    }

    if (!interactionId || clickedIds.has(item.id) || inFlightIds.current.has(item.id)) {
      return;
    }
    inFlightIds.current.add(item.id);
    setClickedIds((prev) => new Set(prev).add(item.id));

    api.recordRecommendationClick(interactionId, item.id, item.source).catch(() => {
      // 클릭 기록 실패는 조용히 무시한다 - 사용자는 이미 이동했거나
      // 이동할 것이고, 이 신호 하나가 없다고 화면에 문제가 생기면 안 된다.
    });
  };

  return (
    <main className="min-h-screen bg-cream">
      <div className="mx-auto flex max-w-2xl flex-col items-center px-6 py-14 text-center sm:py-16">
        <span className="rounded-full bg-coral/10 px-4 py-1.5 text-xs font-medium text-coral-dark">
          AI 여행 안내원
        </span>
        <h1 className="mt-5 font-display text-[28px] font-normal leading-snug text-coral-dark sm:text-[34px]">
          영종도에서 뭐 할까?
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-ink-muted sm:text-[15px]">
          지금 영종 AI에 등록된 업체 중에서 딱 맞는 곳을 추천해 드려요.
        </p>

        <div className="mt-8 w-full">
          <ChatWidget
            greeting="안녕하세요! 어떤 곳을 찾고 계신가요? 예를 들어 '바다 보이는 카페', '아이랑 갈 곳', '강아지랑 묵을 숙소' 처럼 편하게 물어보세요."
            placeholder="예: 바다 보이는 카페 가고 싶어"
            onSend={handleSend}
          />
        </div>

        {recommendations.length > 0 && (
          <div className="mt-9 w-full text-left">
            <h2 className="mb-3 text-xs font-semibold tracking-wide text-ink-muted">추천 목록</h2>
            <ul className="flex flex-col gap-2.5">
              {recommendations.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => handleRecommendationClick(item)}
                    disabled={clickedIds.has(item.id)}
                    className="w-full rounded-2xl border border-ink/10 bg-white p-4 text-left transition hover:border-coral/40 disabled:cursor-default disabled:opacity-60"
                  >
                    <p className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-ink">{item.name}</span>
                      <span className="rounded-full bg-coral/10 px-2.5 py-0.5 text-[11px] font-medium text-coral-dark">
                        {categoryLabel(item.category)}
                      </span>
                    </p>
                    <p className="mt-1 text-[13.5px] leading-relaxed text-ink-muted">{item.reason}</p>
                    {item.source === "business" ? (
                      <p className="mt-1.5 flex items-center gap-1 text-xs text-ink-muted/60">
                        클릭하면 업체 페이지로 이동해요
                        <ArrowIcon />
                      </p>
                    ) : (
                      <p className="mt-1.5 text-xs text-ink-muted/60">관광지 정보 (등록된 업체 페이지는 없어요)</p>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </main>
  );
}
