"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ChatWidget } from "@/components/ChatWidget";
import { api } from "@/lib/api";

export default function ManagerChatPage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  if (!token) return null;
  const authToken = token;

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">AI 직원에게 물어보기</h1>
      <p className="mb-8 text-sm text-gray-600">
        이번 달 성과, 쿠폰 상태, 연관업체 제안 현황을 바탕으로 답해드려요. 아직 연동되지 않은
        매출/결제 데이터는 솔직하게 모른다고 답할 거예요.
      </p>
      <ChatWidget
        greeting="안녕하세요, 사장님! 이번 달 어떠세요? 편하게 물어보세요. 예: '이번 달 어때?', '손님 좀 늘려줘'"
        placeholder="예: 손님 좀 늘려줘"
        onSend={async (message) => ({ text: (await api.managerChat(authToken, id, message)).reply })}
      />
    </main>
  );
}
