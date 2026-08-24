"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, CATEGORY_LABELS, type IncomingPartnerInvite, type PartnerSuggestion } from "@/lib/api";

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
  const [messagingId, setMessagingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copiedLinkId, setCopiedLinkId] = useState<string | null>(null);

  const [incoming, setIncoming] = useState<IncomingPartnerInvite[] | null>(null);
  const [respondingId, setRespondingId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    api
      .listExpansion(token, id)
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
    api
      .listIncomingExpansionInvites(token, id)
      .then(setIncoming)
      .catch(() => setIncoming([]));
  }, [id, token]);

  const onRespond = async (senderId: string, accept: boolean) => {
    if (!token) return;
    setRespondingId(senderId);
    try {
      accept
        ? await api.acceptExpansionInvite(token, id, senderId)
        : await api.rejectExpansionInvite(token, id, senderId);
      setIncoming((prev) => prev?.filter((i) => i.business_a_id !== senderId) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "제휴 제안 응답 중 오류가 발생했습니다.");
    } finally {
      setRespondingId(null);
    }
  };

  const updateSuggestion = (updated: PartnerSuggestion) => {
    setSuggestions((prev) => prev?.map((s) => (s.business_b_id === updated.business_b_id ? updated : s)) ?? null);
  };

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
      updateSuggestion(await api.inviteExpansionPartner(token, id, partnerId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "제휴 제안 처리 중 오류가 발생했습니다.");
    } finally {
      setInvitingId(null);
    }
  };

  const onGenerateMessage = async (partnerId: string) => {
    if (!token) return;
    setMessagingId(partnerId);
    try {
      updateSuggestion(await api.generateExpansionMessage(token, id, partnerId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "메시지 생성 중 오류가 발생했습니다.");
    } finally {
      setMessagingId(null);
    }
  };

  const onCopy = async (partnerId: string, message: string) => {
    try {
      await navigator.clipboard.writeText(message);
      setCopiedId(partnerId);
      setTimeout(() => setCopiedId((prev) => (prev === partnerId ? null : prev)), 2000);
    } catch {
      // clipboard API unavailable - the text is still visible to select/copy manually
    }
  };

  const onCopyInviteLink = async (partnerId: string, referralToken: string) => {
    const link = `${window.location.origin}/join/${referralToken}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopiedLinkId(partnerId);
      setTimeout(() => setCopiedLinkId((prev) => (prev === partnerId ? null : prev)), 2000);
    } catch {
      // clipboard API unavailable - not fatal, the button just won't confirm
    }
  };

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">연관업체 추천</h1>
      <p className="mb-8 text-sm text-gray-600">
        AI가 실제 등록된 업체 중에서 우리 가게와 함께하면 좋을 곳을 찾아드려요. 손님 동선이 자연스럽게
        이어지는 다른 업종의 가게를 추천해요.
      </p>

      {incoming && incoming.length > 0 && (
        <section className="mb-8 rounded-md border border-gray-200 p-4">
          <h2 className="mb-3 font-semibold">받은 제휴 제안</h2>
          <p className="mb-3 text-sm text-gray-600">
            수락하면 서로의 손님 AI 대화에서 자연스럽게 서로를 추천해줘요.
          </p>
          <ul className="flex flex-col gap-3">
            {incoming.map((invite) => (
              <li key={invite.business_a_id} className="rounded-md bg-gray-50 p-3 text-sm">
                <p className="font-semibold">
                  {invite.name_ko}{" "}
                  <span className="font-normal text-gray-500">
                    · {CATEGORY_LABELS[invite.category]} · 적합도 {invite.score}
                  </span>
                </p>
                <p className="mt-1 text-gray-600">{invite.reason}</p>
                {invite.invite_message && (
                  <p className="mt-2 whitespace-pre-wrap rounded-md bg-white p-2 text-gray-700">
                    {invite.invite_message}
                  </p>
                )}
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => onRespond(invite.business_a_id, true)}
                    disabled={respondingId === invite.business_a_id}
                    className="rounded-md bg-black px-3 py-1.5 text-white disabled:opacity-50"
                  >
                    수락하기
                  </button>
                  <button
                    onClick={() => onRespond(invite.business_a_id, false)}
                    disabled={respondingId === invite.business_a_id}
                    className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
                  >
                    보류하기
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

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

              {s.referral_token && (
                <button
                  onClick={() => onCopyInviteLink(s.business_b_id, s.referral_token!)}
                  className="mt-2 text-xs underline"
                >
                  {copiedLinkId === s.business_b_id ? "초대 링크 복사됨!" : "초대 링크 복사하기"}
                </button>
              )}

              {s.invite_message ? (
                <div className="mt-3 rounded-md bg-gray-50 p-3">
                  <p className="whitespace-pre-wrap text-gray-700">{s.invite_message}</p>
                  <div className="mt-2 flex gap-3">
                    <button
                      onClick={() => onCopy(s.business_b_id, s.invite_message!)}
                      className="text-xs underline"
                    >
                      {copiedId === s.business_b_id ? "복사됨!" : "복사하기"}
                    </button>
                    <button
                      onClick={() => onGenerateMessage(s.business_b_id)}
                      disabled={messagingId === s.business_b_id}
                      className="text-xs underline disabled:opacity-50"
                    >
                      다시 만들기
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => onGenerateMessage(s.business_b_id)}
                  disabled={messagingId === s.business_b_id}
                  className="mt-3 text-xs underline disabled:opacity-50"
                >
                  {messagingId === s.business_b_id ? "메시지 만드는 중..." : "제안 메시지 만들기"}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
