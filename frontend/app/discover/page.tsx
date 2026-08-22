"use client";

import { ChatWidget } from "@/components/ChatWidget";
import { api } from "@/lib/api";

export default function DiscoverPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">영종도에서 뭐 할까?</h1>
      <p className="mb-8 text-sm text-gray-600">
        지금 영종 AI에 등록된 업체 중에서 딱 맞는 곳을 추천해 드려요.
      </p>
      <ChatWidget
        greeting="안녕하세요! 어떤 곳을 찾고 계신가요? 예를 들어 '바다 보이는 카페', '아이랑 갈 곳', '강아지랑 묵을 숙소' 처럼 편하게 물어보세요."
        placeholder="예: 바다 보이는 카페 가고 싶어"
        onSend={async (message) => (await api.recommend(message)).reply}
      />
    </main>
  );
}
