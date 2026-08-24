"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  ApiError,
  PILOT_STATUS_LABELS,
  type AdminAiInteractionSummary,
  type AdminAiMessageDetail,
  type AdminBusiness,
  type AdminKpi,
  type AdminStats,
  type AdminUser,
  type BusinessGraphEdge,
  type BusinessStatus,
  type PilotStatus,
  type TouristPlace,
} from "@/lib/api";

const STATUS_LABEL: Record<BusinessStatus, string> = {
  DRAFT: "준비 중",
  ACTIVE: "공개 중",
  DISABLED: "비활성화됨",
};

const TOURIST_STATUS_LABEL: Record<string, string> = {
  VERIFIED: "확인 완료",
  UNVERIFIED: "확인 전",
  EXPIRED: "기간 만료",
  DISABLED: "비활성화됨",
};

const ATTRIBUTION_LABEL: Record<string, string> = {
  DIRECT: "쿠폰으로 확인",
  ASSISTED: "예약으로 확인",
  UNKNOWN: "확인 안 됨",
};

const USER_ROLE_LABEL: Record<string, string> = {
  BUSINESS_OWNER: "사장님",
  CUSTOMER: "손님",
  ADMIN: "관리자",
  PARTNER_MANAGER: "제휴 담당자",
};

const RESERVATION_STATUS_LABEL: Record<string, string> = {
  REQUESTED: "요청됨",
  CONFIRMED: "확정됨",
  CANCELLED: "취소됨",
  COMPLETED: "방문 완료",
  NO_SHOW: "노쇼",
};

const PARTNER_RELATIONSHIP_STATUS_LABEL: Record<string, string> = {
  SUGGESTED: "제안됨",
  INVITED: "제휴 제안함",
  ACCEPTED: "제휴 성사",
  REJECTED: "보류",
};

const AGENT_TYPE_LABEL: Record<string, string> = {
  manager: "Manager AI",
  customer: "Customer AI",
  chef: "Chef AI",
  info: "Info AI",
  expansion: "Expansion AI",
  profile_draft: "소개글 초안 AI",
  referral_message: "제휴 메시지 AI",
};

function CountTable({ counts, labels }: { counts: Record<string, number>; labels?: Record<string, string> }) {
  const entries = Object.entries(counts);
  if (entries.length === 0) return <p className="text-gray-500">데이터 없음</p>;
  return (
    <ul className="flex flex-wrap gap-3 text-sm">
      {entries.map(([key, value]) => (
        <li key={key} className="rounded-md bg-gray-100 px-3 py-1">
          {labels?.[key] ?? key} <span className="font-semibold">{value}</span>
        </li>
      ))}
    </ul>
  );
}

export default function AdminPage() {
  const { token, user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [kpi, setKpi] = useState<AdminKpi | null>(null);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [businesses, setBusinesses] = useState<AdminBusiness[] | null>(null);
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [aiSummary, setAiSummary] = useState<AdminAiInteractionSummary[] | null>(null);
  const [recentMessages, setRecentMessages] = useState<AdminAiMessageDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const [businessGraph, setBusinessGraph] = useState<BusinessGraphEdge[] | null>(null);

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
    api.adminKpi(token).then(setKpi).catch(() => setKpi(null));
    api.adminStats(token).then(setStats).catch(() => setStats(null));
    api.adminListBusinesses(token).then(setBusinesses).catch(() => setBusinesses([]));
    api.adminListUsers(token).then(setUsers).catch(() => setUsers([]));
    api.adminAiInteractionSummary(token).then(setAiSummary).catch(() => setAiSummary([]));
    api.adminRecentAiInteractions(token).then(setRecentMessages).catch(() => setRecentMessages([]));
    api.adminListTouristPlaces(token).then(setTouristPlaces).catch(() => setTouristPlaces([]));
    api.adminBusinessGraph(token).then(setBusinessGraph).catch(() => setBusinessGraph([]));
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

  const setBusinessStatus = async (business: AdminBusiness, nextStatus: BusinessStatus) => {
    if (!token) return;
    setError(null);
    setTogglingId(business.id);
    try {
      const updated = await api.adminUpdateBusinessStatus(token, business.id, nextStatus);
      setBusinesses((prev) => prev?.map((b) => (b.id === updated.id ? updated : b)) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "상태 변경 중 오류가 발생했습니다.");
    } finally {
      setTogglingId(null);
    }
  };

  const toggleDisabled = (business: AdminBusiness) =>
    setBusinessStatus(business, business.status === "DISABLED" ? "ACTIVE" : "DISABLED");

  const onChangePilotStatus = async (business: AdminBusiness, pilotStatus: PilotStatus | null) => {
    if (!token) return;
    setError(null);
    setTogglingId(business.id);
    try {
      const updated = await api.updatePilotStatus(token, business.id, pilotStatus);
      setBusinesses((prev) => prev?.map((b) => (b.id === updated.id ? updated : b)) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "파일럿 상태 변경 중 오류가 발생했습니다.");
    } finally {
      setTogglingId(null);
    }
  };

  if (authLoading || !user || user.role !== "ADMIN") return null;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold">관리자</h1>
        <Link href="/admin/pilot" className="rounded-md border border-black px-4 py-2 text-sm">
          파일럿 운영 현황 →
        </Link>
      </div>
      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      <section className="mb-10">
        <h2 className="mb-1 font-semibold">한눈에 보는 숫자</h2>
        <p className="mb-3 text-sm text-gray-600">
          많은 숫자를 다 보지 않고, 이 7개만 본다. 가장 중요한 숫자는 맨 아래 강조된 값이에요.
        </p>
        {kpi === null ? (
          <p className="text-gray-500">불러오는 중...</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-md border border-gray-200 p-3 text-center">
                <p className="text-xl font-bold">{kpi.signed_up_businesses.toLocaleString()}</p>
                <p className="mt-1 text-xs text-gray-500">가입 업체 수</p>
              </div>
              <div className="rounded-md border border-gray-200 p-3 text-center">
                <p className="text-xl font-bold">{kpi.active_owner_ai_last_30d.toLocaleString()}</p>
                <p className="mt-1 text-xs text-gray-500">최근 30일 AI 쓴 사장님 수</p>
              </div>
              <div className="rounded-md border border-gray-200 p-3 text-center">
                <p className="text-xl font-bold">{kpi.ai_response_count_last_30d.toLocaleString()}</p>
                <p className="mt-1 text-xs text-gray-500">AI가 답한 횟수 (30일)</p>
              </div>
              <div className="rounded-md border border-gray-200 p-3 text-center">
                <p className="text-xl font-bold">{kpi.ai_recommendation_count_last_30d.toLocaleString()}</p>
                <p className="mt-1 text-xs text-gray-500">AI가 추천한 횟수 (30일)</p>
              </div>
              <div className="rounded-md border border-gray-200 p-3 text-center">
                <p className="text-xl font-bold">
                  {kpi.coupon_conversion_rate !== null
                    ? `${(kpi.coupon_conversion_rate * 100).toFixed(0)}%`
                    : "-"}{" "}
                  /{" "}
                  {kpi.reservation_conversion_rate !== null
                    ? `${(kpi.reservation_conversion_rate * 100).toFixed(0)}%`
                    : "-"}
                </p>
                <p className="mt-1 text-xs text-gray-500">쿠폰 사용 비율 / 예약 성사율</p>
              </div>
              <div className="rounded-md border border-gray-200 p-3 text-center">
                <p className="text-xl font-bold">{kpi.actual_visits.toLocaleString()}</p>
                <p className="mt-1 text-xs text-gray-500">실제 방문 수</p>
              </div>
            </div>
            <div className="rounded-md border-2 border-black p-4 text-center">
              <p className="text-3xl font-bold">{Number(kpi.ai_connected_revenue).toLocaleString()}원</p>
              <p className="mt-1 text-sm text-gray-600">
                AI 추천으로 이어진 매출 — AI가 실제로 만들어낸 확인 가능한 매출
              </p>
            </div>
          </div>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 font-semibold">전체 통계 자세히 보기</h2>
        {stats === null ? (
          <p className="text-gray-500">불러오는 중...</p>
        ) : (
          <div className="flex flex-col gap-3 text-sm">
            <div>
              <p className="mb-1 text-gray-500">업체 상태</p>
              <CountTable counts={stats.businesses_by_status} labels={STATUS_LABEL} />
            </div>
            <div>
              <p className="mb-1 text-gray-500">유저 역할</p>
              <CountTable counts={stats.users_by_role} labels={USER_ROLE_LABEL} />
            </div>
            <div>
              <p className="mb-1 text-gray-500">예약 상태</p>
              <CountTable counts={stats.reservations_by_status} labels={RESERVATION_STATUS_LABEL} />
            </div>
            <div>
              <p className="mb-1 text-gray-500">업체 간 협력 현황</p>
              <CountTable counts={stats.partner_relationships_by_status} labels={PARTNER_RELATIONSHIP_STATUS_LABEL} />
            </div>
            <p className="text-gray-700">
              쿠폰 발급 {stats.coupons_issued}건 · 사용 {stats.coupons_redeemed}건
            </p>
            <p className="text-gray-700">최근 30일 AI가 답한 횟수 {stats.ai_interactions_last_30d}건</p>
            <div>
              <p className="mb-1 text-gray-500">AI별 응대 현황 (전체 기간)</p>
              <CountTable counts={stats.ai_interactions_by_agent_type} labels={AGENT_TYPE_LABEL} />
            </div>
            <div className="rounded-md border border-gray-200 p-3">
              <p className="font-semibold">확인된 거래</p>
              <p className="mt-1 text-gray-700">
                방문확인 {stats.transactions_count}건 · 확인 거래액{" "}
                {Number(stats.transactions_total_amount).toLocaleString()}원
              </p>
              <p className="mt-1 text-gray-700">
                AI 추천으로 이어진 매출 {Number(stats.transactions_ai_connected_amount).toLocaleString()}원
              </p>
              <ul className="mt-1 flex flex-wrap gap-3 text-xs text-gray-500">
                {Object.entries(stats.transactions_amount_by_attribution).map(([attribution, amount]) => (
                  <li key={attribution}>
                    {ATTRIBUTION_LABEL[attribution] ?? attribution} {Number(amount).toLocaleString()}원
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-gray-500">
                쿠폰으로 확인 = 쿠폰 사용으로 연결 확인됨, 예약으로 확인 = 예약 완료로 연결 확인됨,
                확인 안 됨 = 실제 거래이지만 AI와의 연결은 확인 불가 - 단순 추천은 매출로 계산하지
                않아요.
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
                    {b.owner_email ?? "주인 없음"} · {STATUS_LABEL[b.status]}
                  </p>
                </div>
                <div className="flex gap-2">
                  {b.status === "DRAFT" && (
                    <button
                      onClick={() => setBusinessStatus(b, "ACTIVE")}
                      disabled={togglingId === b.id}
                      className="rounded-md bg-black px-3 py-1.5 text-white disabled:opacity-50"
                    >
                      공개하기
                    </button>
                  )}
                  <button
                    onClick={() => toggleDisabled(b)}
                    disabled={togglingId === b.id}
                    className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
                  >
                    {b.status === "DISABLED" ? "재활성화" : "비활성화"}
                  </button>
                  <select
                    value={b.pilot_status ?? ""}
                    disabled={togglingId === b.id}
                    onChange={(e) => onChangePilotStatus(b, (e.target.value || null) as PilotStatus | null)}
                    className="rounded-md border border-gray-300 px-2 py-1.5 text-xs"
                  >
                    <option value="">파일럿 제외</option>
                    {(["PILOT_ACTIVE", "PILOT_PAUSED", "PILOT_COMPLETED"] as PilotStatus[]).map((s) => (
                      <option key={s} value={s}>
                        {PILOT_STATUS_LABELS[s]}
                      </option>
                    ))}
                  </select>
                </div>
              </li>
            ))}
            {businesses.length === 0 && <p className="text-gray-500">업체가 없어요.</p>}
          </ul>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 font-semibold">우리 동네 업체 연결망</h2>
        <p className="mb-3 text-sm text-gray-600">
          확장AI가 만든 업체 간 연결 전체 - 누가 누구와 제휴를 제안했고, 어떤 상태인지 한눈에
          봐요.
        </p>
        {businessGraph === null ? (
          <p className="text-gray-500">불러오는 중...</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {businessGraph.map((edge, i) => (
              <li
                key={i}
                className="flex items-center justify-between rounded-md border border-gray-200 p-3"
              >
                <span>
                  {edge.business_a_name} {edge.relationship_type === "NEAR" ? "↔" : "→"} {edge.business_b_name}{" "}
                  <span className="text-gray-500">
                    {edge.relationship_type === "NEAR"
                      ? `(약 ${edge.distance_m}m)`
                      : `(어울리는 정도 ${edge.score})`}
                  </span>
                </span>
                <span className="text-xs text-gray-500">
                  {edge.relationship_type === "NEAR" ? "가까운 업체" : edge.status}
                </span>
              </li>
            ))}
            {businessGraph.length === 0 && <p className="text-gray-500">아직 연결 데이터가 없어요.</p>}
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
        <h2 className="mb-3 font-semibold">관광지 정보 관리 (AI가 답할 때 쓰는 자료)</h2>
        <p className="mb-3 text-sm text-gray-500">
          여기서 확인 완료로 표시한 곳만 방문객 AI가 추천에 사용해요. 실제 출처(공식 기관, 직접 확인 등)를
          확인한 곳만 확인 완료로 표시해주세요 — AI가 스스로 지어내지 않도록 하는 안전장치예요.
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
                    {TOURIST_STATUS_LABEL[p.status] ?? p.status} {p.source_name && `· 출처: ${p.source_name}`}
                  </p>
                </div>
                <button
                  onClick={() => onToggleVerified(p)}
                  disabled={verifyingId === p.id}
                  className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
                >
                  {p.status === "VERIFIED" ? "확인 취소" : "확인 완료로 표시"}
                </button>
              </li>
            ))}
            {touristPlaces.length === 0 && <p className="text-gray-500">등록된 관광지가 없어요.</p>}
          </ul>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-3 font-semibold">AI별 응대 현황 (업체별 건수)</h2>
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
