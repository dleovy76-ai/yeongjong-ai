"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatWidget } from "@/components/ChatWidget";
import { api, CATEGORY_LABELS, type BusinessCategory, type RecommendationItem } from "@/lib/api";

function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category as BusinessCategory] ?? category;
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
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">영종도에서 뭐 할까?</h1>
      <p className="mb-8 text-sm text-gray-600">
        지금 영종 AI에 등록된 업체 중에서 딱 맞는 곳을 추천해 드려요.
      </p>
      <ChatWidget
        greeting="안녕하세요! 어떤 곳을 찾고 계신가요? 예를 들어 '바다 보이는 카페', '아이랑 갈 곳', '강아지랑 묵을 숙소' 처럼 편하게 물어보세요."
        placeholder="예: 바다 보이는 카페 가고 싶어"
        onSend={handleSend}
      />

      {recommendations.length > 0 && (
        <div className="mt-6">
          <h2 className="mb-3 text-sm font-semibold text-gray-600">추천 목록</h2>
          <ul className="flex flex-col gap-2">
            {recommendations.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => handleRecommendationClick(item)}
                  disabled={clickedIds.has(item.id)}
                  className="w-full rounded-md border border-gray-200 p-3 text-left text-sm transition hover:border-black disabled:cursor-default disabled:opacity-60"
                >
                  <p className="font-semibold">
                    {item.name}
                    <span className="ml-2 text-xs font-normal text-gray-500">{categoryLabel(item.category)}</span>
                  </p>
                  <p className="mt-1 text-gray-600">{item.reason}</p>
                  {item.source === "business" ? (
                    <p className="mt-1 text-xs text-gray-400">클릭하면 업체 페이지로 이동해요</p>
                  ) : (
                    <p className="mt-1 text-xs text-gray-400">관광지 정보 (등록된 업체 페이지는 없어요)</p>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
