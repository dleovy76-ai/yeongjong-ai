"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, CATEGORY_LABELS, type PartnerSuggestion } from "@/lib/api";

const STATUS_LABEL: Record<PartnerSuggestion["status"], string> = {
  SUGGESTED: "제안됨",
  INVITED: "제휴 제안함",
  ACCEPTED: "제휴 성사",
  REJECTED: "보류",
};

export default function ExpansionPage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();

  const [suggestions, setSuggestions] = useState<PartnerSuggestion[] | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [invitingId, setInvitingId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    api
      .listExpansion(token, id)
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, [id, token]);

  const onAnalyze = async () => {
    if (!token) return;
    setError(null);
    setAnalyzing(true);
    try {
      setSuggestions(await api.analyzeExpansion(token, id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "분석 중 오류가 발생했습니다.");
    } finally {
      setAnalyzing(false);
    }
  };

  const onInvite = async (partnerId: string) => {
    if (!token) return;
    setInvitingId(partnerId);
    try {
      const updated = await api.inviteExpansionPartner(token, id, partnerId);
      setSuggestions((prev) => prev?.map((s) => (s.business_b_id === partnerId ? updated : s)) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "제휴 제안 처리 중 오류가 발생했습니다.");
    } finally {
      setInvitingId(null);
    }
  };

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">연관업체 추천</h1>
      <p className="mb-8 text-sm text-gray-600">
        AI가 실제 등록된 업체 중에서 우리 가게와 함께하면 좋을 곳을 찾아드려요. 손님 동선이 자연스럽게
        이어지는 다른 업종의 가게를 추천해요.
      </p>

      <button
        onClick={onAnalyze}
        disabled={analyzing}
        className="mb-8 rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
      >
        {analyzing ? "분석 중..." : "연관업체 다시 분석하기"}
      </button>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {suggestions === null ? (
        <p className="text-gray-500">불러오는 중...</p>
      ) : suggestions.length === 0 ? (
        <p className="text-gray-500">
          아직 추천 결과가 없어요. 위 버튼으로 분석을 시작해 보세요.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {suggestions.map((s) => (
            <li key={s.business_b_id} className="rounded-md border border-gray-200 p-4 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold">
                    {s.name_ko}{" "}
                    <span className="font-normal text-gray-500">
                      · {CATEGORY_LABELS[s.category]} · 적합도 {s.score}
                    </span>
                  </p>
                  <p className="mt-1 text-gray-600">{s.reason}</p>
                  <p className="mt-1 text-xs text-gray-400">
                    {s.is_claimed ? "이미 영종 AI 사용 중" : "아직 미등록 업체"} · {STATUS_LABEL[s.status]}
                  </p>
                </div>
                {s.status === "SUGGESTED" && (
                  <button
                    onClick={() => onInvite(s.business_b_id)}
                    disabled={invitingId === s.business_b_id}
                    className="shrink-0 rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
                  >
                    제휴 제안하기
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
