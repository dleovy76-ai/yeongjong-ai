"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  ApiError,
  type AdminAiInteractionSummary,
  type AdminAiMessageDetail,
  type AdminBusiness,
  type AdminStats,
  type AdminUser,
  type BusinessStatus,
  type TouristPlace,
} from "@/lib/api";

const STATUS_LABEL: Record<BusinessStatus, string> = {
  DRAFT: "준비 중",
  ACTIVE: "공개 중",
  DISABLED: "비활성화됨",
};

function CountTable({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  if (entries.length === 0) return <p className="text-gray-500">데이터 없음</p>;
  return (
    <ul className="flex flex-wrap gap-3 text-sm">
      {entries.map(([key, value]) => (
        <li key={key} className="rounded-md bg-gray-100 px-3 py-1">
          {key} <span className="font-semibold">{value}</span>
        </li>
      ))}
    </ul>
  );
}

export default function AdminPage() {
  const { token, user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [businesses, setBusinesses] = useState<AdminBusiness[] | null>(null);
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [aiSummary, setAiSummary] = useState<AdminAiInteractionSummary[] | null>(null);
  const [recentMessages, setRecentMessages] = useState<AdminAiMessageDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const [touristPlaces, setTouristPlaces] = useState<TouristPlace[] | null>(null);
  const [placeName, setPlaceName] = useState("");
  const [placeCategory, setPlaceCategory] = useState("");
  const [placeSource, setPlaceSource] = useState("");
  const [placeSubmitting, setPlaceSubmitting] = useState(false);
  const [placeError, setPlaceError] = useState<string | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!token || user?.role !== "ADMIN") {
      router.push("/");
    }
  }, [authLoading, token, user, router]);

  useEffect(() => {
    if (!token || user?.role !== "ADMIN") return;
    api.adminStats(token).then(setStats).catch(() => setStats(null));
    api.adminListBusinesses(token).then(setBusinesses).catch(() => setBusinesses([]));
    api.adminListUsers(token).then(setUsers).catch(() => setUsers([]));
    api.adminAiInteractionSummary(token).then(setAiSummary).catch(() => setAiSummary([]));
    api.adminRecentAiInteractions(token).then(setRecentMessages).catch(() => setRecentMessages([]));
    api.adminListTouristPlaces(token).then(setTouristPlaces).catch(() => setTouristPlaces([]));
  }, [token, user]);

  const onAddTouristPlace = async (e: FormEvent) => {
    e.preventDefault();
    if (!token || !placeName.trim() || !placeCategory.trim()) return;
    setPlaceError(null);
    setPlaceSubmitting(true);
    try {
      const created = await api.adminCreateTouristPlace(token, {
        name: placeName.trim(),
        category: placeCategory.trim(),
        source_name: placeSource.trim() || undefined,
      });
      setTouristPlaces((prev) => (prev ? [created, ...prev] : [created]));
      setPlaceName("");
      setPlaceCategory("");
      setPlaceSource("");
    } catch (err) {
      setPlaceError(err instanceof ApiError ? err.message : "추가 중 오류가 발생했습니다.");
    } finally {
      setPlaceSubmitting(false);
    }
  };

  const onToggleVerified = async (place: TouristPlace) => {
    if (!token) return;
    setPlaceError(null);
    setVerifyingId(place.id);
    try {
      const nextStatus = place.status === "VERIFIED" ? "UNVERIFIED" : "VERIFIED";
      const updated = await api.adminUpdateTouristPlace(token, place.id, { status: nextStatus });
      setTouristPlaces((prev) => prev?.map((p) => (p.id === updated.id ? updated : p)) ?? null);
    } catch (err) {
      setPlaceError(err instanceof ApiError ? err.message : "상태 변경 중 오류가 발생했습니다.");
    } finally {
      setVerifyingId(null);
    }
  };

  const toggleDisabled = async (business: AdminBusiness) => {
    if (!token) return;
    setError(null);
    setTogglingId(business.id);
    try {
      const nextStatus = business.status === "DISABLED" ? "DRAFT" : "DISABLED";
      const updated = await api.adminUpdateBusinessStatus(token, business.id, nextStatus);
      setBusinesses((prev) => prev?.map((b) => (b.id === updated.id ? updated : b)) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "상태 변경 중 오류가 발생했습니다.");
    } finally {
      setTogglingId(null);
    }
  };

  if (authLoading || !user || user.role !== "ADMIN") return null;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="mb-8 text-2xl font-bold">관리자</h1>
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <section className="mb-10">
        <h2 className="mb-3 font-semibold">현황</h2>
        {stats === null ? (
          <p className="text-gray-500">불러오는 중...</p>
        ) : (
          <div className="flex flex-col gap-3 text-sm">
            <div>
              <p className="mb-1 text-gray-500">업체 상태</p>
              <CountTable counts={stats.businesses_by_status} />
            </div>
            <div>
              <p className="mb-1 text-gray-500">유저 역할</p>
              <CountTable counts={stats.users_by_role} />
            </div>
            <div>
              <p className="mb-1 text-gray-500">예약 상태</p>
              <CountTable counts={stats.reservations_by_status} />
            </div>
            <div>
              <p className="mb-1 text-gray-500">파트너 제휴 상태</p>
              <CountTable counts={stats.partner_relationships_by_status} />
            </div>
            <p className="text-gray-700">
              쿠폰 발급 {stats.coupons_issued}건 · 사용 {stats.coupons_redeemed}건
            </p>
            <p className="text-gray-700">최근 30일 AI 응대 {stats.ai_interactions_last_30d}건</p>
            <div>
              <p className="mb-1 text-gray-500">AI 응대 유형별 (전체 기간)</p>
              <CountTable counts={stats.ai_interactions_by_agent_type} />
            </div>
            <div className="rounded-md border border-gray-200 p-3">
              <p className="font-semibold">확인된 거래</p>
              <p className="mt-1 text-gray-700">
                방문확인 {stats.transactions_count}건 · 확인 거래액{" "}
                {Number(stats.transactions_total_amount).toLocaleString()}원
              </p>
              <p className="mt-1 text-gray-500">
                그중 AI 연관(쿠폰 사용/예약 완료로 연결 확인된) 거래액{" "}
                {Number(stats.transactions_direct_ai_attributed_amount).toLocaleString()}원 - 단순
                추천은 매출로 계산하지 않아요.
              </p>
            </div>
          </div>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 font-semibold">업체 관리</h2>
        {businesses === null ? (
          <p className="text-gray-500">불러오는 중...</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {businesses.map((b) => (
              <li key={b.id} className="flex items-center justify-between rounded-md border border-gray-200 p-3 text-sm">
                <div>
                  <p className="font-semibold">{b.name_ko}</p>
                  <p className="text-gray-500">
                    {b.owner_email ?? "미claim"} · {STATUS_LABEL[b.status]}
                  </p>
                </div>
                <button
                  onClick={() => toggleDisabled(b)}
                  disabled={togglingId === b.id}
                  className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
                >
                  {b.status === "DISABLED" ? "재활성화" : "비활성화"}
                </button>
              </li>
            ))}
            {businesses.length === 0 && <p className="text-gray-500">업체가 없어요.</p>}
          </ul>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 font-semibold">유저 목록</h2>
        {users === null ? (
          <p className="text-gray-500">불러오는 중...</p>
        ) : (
          <ul className="flex flex-col gap-1 text-sm">
            {users.map((u) => (
              <li key={u.id} className="flex justify-between border-b border-gray-100 py-1">
                <span>{u.name}</span>
                <span className="text-gray-500">
                  {u.email} · {u.role}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 font-semibold">관광지 관리 (Info AI 근거 데이터)</h2>
        <p className="mb-3 text-sm text-gray-500">
          여기서 검증(VERIFIED)한 곳만 방문객 AI가 추천에 사용해요. 실제 출처(공식 기관, 직접 확인 등)를
          확인한 곳만 검증 처리해주세요 — AI가 스스로 지어내지 않도록 하는 안전장치예요.
        </p>
        <form onSubmit={onAddTouristPlace} className="mb-4 flex flex-wrap gap-2">
          <input
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            placeholder="이름 (예: 을왕리해수욕장)"
            value={placeName}
            onChange={(e) => setPlaceName(e.target.value)}
          />
          <input
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            placeholder="분류 (예: 해변)"
            value={placeCategory}
            onChange={(e) => setPlaceCategory(e.target.value)}
          />
          <input
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
            placeholder="출처 (예: 인천 중구청, 직접 확인)"
            value={placeSource}
            onChange={(e) => setPlaceSource(e.target.value)}
          />
          <button
            type="submit"
            disabled={placeSubmitting}
            className="rounded-md bg-black px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            {placeSubmitting ? "추가 중..." : "추가"}
          </button>
        </form>
        {placeError && <p className="mb-2 text-sm text-red-600">{placeError}</p>}
        {touristPlaces === null ? (
          <p className="text-gray-500">불러오는 중...</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {touristPlaces.map((p) => (
              <li
                key={p.id}
                className="flex items-center justify-between rounded-md border border-gray-200 p-3 text-sm"
              >
                <div>
                  <p className="font-semibold">
                    {p.name} <span className="font-normal text-gray-500">· {p.category}</span>
                  </p>
                  <p className="text-gray-500">
                    {p.status} {p.source_name && `· 출처: ${p.source_name}`}
                  </p>
                </div>
                <button
                  onClick={() => onToggleVerified(p)}
                  disabled={verifyingId === p.id}
                  className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
                >
                  {p.status === "VERIFIED" ? "검증 해제" : "검증 완료로 표시"}
                </button>
              </li>
            ))}
            {touristPlaces.length === 0 && <p className="text-gray-500">등록된 관광지가 없어요.</p>}
          </ul>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 font-semibold">AI 응대 현황 (업체·에이전트별 건수)</h2>
        <p className="mb-3 text-sm text-gray-500">
          건수 기준으로 비정상적으로 많은 업체가 있는지 빠르게 훑어볼 수 있어요. 실제 대화 내용은 아래
          &quot;최근 AI 대화&quot;에서 볼 수 있어요.
        </p>
        {aiSummary === null ? (
          <p className="text-gray-500">불러오는 중...</p>
        ) : (
          <ul className="flex flex-col gap-1 text-sm">
            {aiSummary.map((row, i) => (
              <li key={i} className="flex justify-between border-b border-gray-100 py-1">
                <span>{row.business_name ?? "(업체 무관)"}</span>
                <span className="text-gray-500">
                  {row.agent_type} · {row.count}건
                </span>
              </li>
            ))}
            {aiSummary.length === 0 && <p className="text-gray-500">아직 AI 응대 기록이 없어요.</p>}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-3 font-semibold">최근 AI 대화</h2>
        <p className="mb-3 text-sm text-gray-500">
          최근 50건의 실제 질문·답변이에요. 비용은 요금을 설정한 경우에만 표시돼요.
        </p>
        {recentMessages === null ? (
          <p className="text-gray-500">불러오는 중...</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {recentMessages.map((m) => (
              <li key={m.id} className="rounded-md border border-gray-200 p-3 text-sm">
                <p className="mb-1 text-gray-500">
                  {m.business_name ?? "(업체 무관)"} · {m.agent_type} ·{" "}
                  {new Date(m.created_at).toLocaleString("ko-KR")}
                </p>
                {m.user_message && <p>Q. {m.user_message}</p>}
                {m.reply && <p className="text-gray-700">A. {m.reply}</p>}
                <p className="mt-1 text-xs text-gray-400">
                  토큰 {m.prompt_tokens ?? "-"}/{m.completion_tokens ?? "-"}
                  {m.estimated_cost_usd && ` · $${m.estimated_cost_usd}`}
                </p>
              </li>
            ))}
            {recentMessages.length === 0 && <p className="text-gray-500">아직 AI 응대 기록이 없어요.</p>}
          </ul>
        )}
      </section>
    </main>
  );
}
