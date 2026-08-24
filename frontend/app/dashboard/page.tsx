"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  ApiError,
  type Business,
  type BusinessOwnerProfile,
  type BusinessPilotDashboard,
  type Coupon,
  type Performance,
} from "@/lib/api";

const STATUS_LABEL: Record<Business["status"], string> = {
  DRAFT: "준비 중 (비공개)",
  ACTIVE: "공개 중",
  DISABLED: "비활성화됨",
};

function formatWon(amount: string): string {
  return `${Number(amount).toLocaleString()}원`;
}

function textOf(value: Record<string, unknown> | null): string {
  if (!value) return "";
  const text = value["text"];
  return typeof text === "string" ? text : "";
}

// ---- Section 1: 오늘 AI가 우리 가게를 위해 한 일 ----
function TodayStatCard({
  icon,
  label,
  value,
  unit,
  emptyNote,
}: {
  icon: string;
  label: string;
  value: number;
  unit: string;
  emptyNote: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">
        {icon} {label}
      </p>
      <p className="mt-1 text-2xl font-bold tabular-nums">
        {value.toLocaleString()}
        {unit}
      </p>
      {value === 0 && <p className="mt-1 text-xs text-gray-400">{emptyNote}</p>}
    </div>
  );
}

// ---- Section 2: 손님이 우리 가게를 만나는 과정 (핵심 Funnel) ----
function FunnelNode({
  icon,
  title,
  value,
  caption,
  isZero,
  emptyNote,
}: {
  icon: string;
  title: string;
  value?: string;
  caption?: string;
  isZero?: boolean;
  emptyNote?: string;
}) {
  return (
    <div className="flex flex-1 flex-col items-center rounded-lg border border-gray-200 bg-white p-4 text-center">
      <span className="text-2xl">{icon}</span>
      <p className="mt-1 text-sm font-semibold">{title}</p>
      {value !== undefined && <p className="mt-1 text-xl font-bold tabular-nums">{value}</p>}
      {caption && <p className="mt-1 text-xs text-gray-400">{caption}</p>}
      {isZero && emptyNote && <p className="mt-1 text-xs text-gray-400">{emptyNote}</p>}
    </div>
  );
}

function FunnelArrow() {
  return (
    <div className="flex items-center justify-center text-gray-300">
      <span className="sm:hidden">↓</span>
      <span className="hidden sm:inline">→</span>
    </div>
  );
}

// ---- Section 4: 지금 사장님이 할 일 ----
interface TodoItem {
  message: string;
  detail: string;
  actionLabel?: string;
  actionHref?: string;
}

function buildTodo(params: {
  ownerProfile: BusinessOwnerProfile;
  couponsCount: number;
  reservationsEverCount: number;
  clicksToday: number;
  couponsIssuedToday: number;
  businessId: string;
}): TodoItem {
  const { ownerProfile, couponsCount, reservationsEverCount, clicksToday, couponsIssuedToday, businessId } = params;

  const profileIncomplete = !ownerProfile.description || !textOf(ownerProfile.opening_hours);
  if (profileIncomplete) {
    return {
      message: "AI가 손님에게 답할 정보가 아직 부족해요.",
      detail: "가게 소개나 영업시간이 비어 있으면 AI가 \"확인이 필요합니다\"라고만 답해요.",
      actionLabel: "가게 정보 채우기",
      actionHref: `/businesses/${businessId}/profile`,
    };
  }

  if (couponsCount === 0) {
    return {
      message: "아직 손님에게 줄 쿠폰이 없어요.",
      detail: "쿠폰이 있으면 AI 추천을 본 손님이 실제 방문으로 더 쉽게 이어져요.",
      actionLabel: "쿠폰 만들기",
      actionHref: `/businesses/${businessId}/coupons`,
    };
  }

  if (reservationsEverCount === 0) {
    return {
      message: "아직 예약이 들어온 적이 없어요.",
      detail: "예약 안내(전화 예약 가능 여부 등)를 정확히 적어두면 AI가 손님에게 더 잘 안내할 수 있어요.",
      actionLabel: "예약 안내 확인하기",
      actionHref: `/businesses/${businessId}/profile`,
    };
  }

  if (clicksToday > 0 && couponsIssuedToday === 0) {
    return {
      message: "오늘 관심을 보인 손님은 있었지만, 아직 쿠폰을 받아가진 않았어요.",
      detail: "손님이 쿠폰을 더 쉽게 받을 수 있도록 쿠폰 조건을 확인해보세요.",
      actionLabel: "쿠폰 확인하기",
      actionHref: `/businesses/${businessId}/coupons`,
    };
  }

  return {
    message: "메뉴와 대표 사진을 최신으로 유지해보세요.",
    detail: "AI가 손님에게 우리 가게를 더 잘 소개할 수 있어요.",
    actionLabel: "가게 정보 확인하기",
    actionHref: `/businesses/${businessId}/profile`,
  };
}

const QUICK_LINKS = (id: string) => [
  { label: "AI에게 물어보기", href: `/businesses/${id}/manager` },
  { label: "우리 가게 성과", href: `/businesses/${id}/performance` },
  { label: "쿠폰 관리", href: `/businesses/${id}/coupons` },
  { label: "예약 관리", href: `/businesses/${id}/reservations` },
  { label: "매출 기록", href: `/businesses/${id}/coupons` },
  { label: "가게 정보", href: `/businesses/${id}/profile` },
  { label: "주변 가게와 함께 성장", href: `/businesses/${id}/expansion` },
];

export default function DashboardPage() {
  const { token, user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [businesses, setBusinesses] = useState<Business[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const [dashToday, setDashToday] = useState<BusinessPilotDashboard | null>(null);
  const [dashAll, setDashAll] = useState<BusinessPilotDashboard | null>(null);
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [ownerProfile, setOwnerProfile] = useState<BusinessOwnerProfile | null>(null);
  const [coupons, setCoupons] = useState<Coupon[] | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [togglingStatus, setTogglingStatus] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      router.push("/login");
      return;
    }
    api
      .myBusinesses(token)
      .then((list) => {
        setBusinesses(list);
        if (list.length > 0) setSelectedId(list[0].id);
      })
      .catch((err) => setListError(err instanceof ApiError ? err.message : "불러오기 실패"));
  }, [authLoading, token, router]);

  const business = businesses?.find((b) => b.id === selectedId) ?? null;

  const loadDetail = useCallback(() => {
    if (!token || !selectedId) return;
    setDetailError(null);
    setDashToday(null);
    setDashAll(null);
    setPerformance(null);
    setOwnerProfile(null);
    setCoupons(null);
    Promise.all([
      api.getBusinessPilotDashboard(token, selectedId, "today"),
      api.getBusinessPilotDashboard(token, selectedId, "all"),
      api.getPerformance(token, selectedId),
      api.getOwnerProfile(token, selectedId),
      api.listCoupons(selectedId, token),
    ])
      .then(([today, all, perf, profile, couponList]) => {
        setDashToday(today);
        setDashAll(all);
        setPerformance(perf);
        setOwnerProfile(profile);
        setCoupons(couponList);
      })
      .catch((err) => setDetailError(err instanceof ApiError ? err.message : "불러오기 실패"));
  }, [token, selectedId]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const toggleStatus = async () => {
    if (!token || !business) return;
    setTogglingStatus(true);
    try {
      const nextStatus = business.status === "ACTIVE" ? "DRAFT" : "ACTIVE";
      const updated = await api.updateBusiness(token, business.id, { status: nextStatus });
      setBusinesses((prev) => prev?.map((b) => (b.id === updated.id ? updated : b)) ?? null);
    } catch (err) {
      setDetailError(err instanceof ApiError ? err.message : "상태 변경 실패");
    } finally {
      setTogglingStatus(false);
    }
  };

  if (authLoading || !user) return null;

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">영종 AI</h1>
          <p className="mt-1 text-sm text-gray-600">사장님, 오늘도 AI가 우리 가게를 알리고 있어요.</p>
        </div>
        <div className="flex gap-2 text-sm">
          <Link href="/businesses/claim" className="rounded-md border border-black px-3 py-1.5">
            우리 가게 찾기
          </Link>
          <Link href="/businesses/new" className="rounded-md bg-black px-3 py-1.5 text-white">
            + 새 업체 등록
          </Link>
        </div>
      </div>

      {listError && <p className="mb-4 text-sm text-red-600">{listError}</p>}

      {businesses === null ? (
        <p className="text-gray-500">불러오는 중...</p>
      ) : businesses.length === 0 ? (
        <p className="text-gray-500">아직 등록한 업체가 없어요. 위 버튼으로 첫 업체를 등록해 보세요.</p>
      ) : (
        <>
          {businesses.length > 1 && (
            <label className="mb-6 flex items-center gap-2 text-sm">
              업체 선택
              <select
                className="rounded-md border border-gray-300 px-3 py-2"
                value={selectedId ?? ""}
                onChange={(e) => setSelectedId(e.target.value)}
              >
                {businesses.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name_ko}
                  </option>
                ))}
              </select>
            </label>
          )}

          {business && (
            <div className="mb-6 flex items-center justify-between rounded-md border border-gray-200 p-3 text-sm">
              <div>
                <span className="font-semibold">{business.name_ko}</span>{" "}
                <span className="text-gray-500">· {STATUS_LABEL[business.status]}</span>
              </div>
              <button
                onClick={toggleStatus}
                disabled={togglingStatus}
                className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
              >
                {business.status === "ACTIVE" ? "비공개로 전환" : "공개하기"}
              </button>
            </div>
          )}

          {detailError && <p className="mb-4 text-sm text-red-600">{detailError}</p>}

          {!dashToday || !dashAll || !performance || !ownerProfile || coupons === null || !business ? (
            <p className="text-gray-500">불러오는 중...</p>
          ) : (
            <>
              {business.status !== "ACTIVE" && (
                <section className="mb-8 rounded-lg border-2 border-black bg-amber-50 p-4 text-sm">
                  <p className="font-semibold">지금 우리 가게는 손님에게 보이지 않아요.</p>
                  <p className="mt-1 text-gray-700">
                    손님이 AI로 우리 가게를 찾을 수 없어요. 공개하면 AI가 손님에게 우리 가게를 추천할 수 있어요.
                  </p>
                  <button
                    onClick={toggleStatus}
                    disabled={togglingStatus}
                    className="mt-3 rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
                  >
                    {togglingStatus ? "변경 중..." : "지금 공개하기"}
                  </button>
                </section>
              )}

              {/* Section 1: 오늘 AI가 우리 가게를 위해 한 일 */}
              <section className="mb-8">
                <h2 className="mb-3 font-semibold">오늘 AI가 우리 가게를 위해 한 일</h2>
                <div className="grid grid-cols-2 gap-3">
                  <TodayStatCard
                    icon="🤖"
                    label="AI 상담"
                    value={dashToday.ai_interactions_total}
                    unit="회"
                    emptyNote="아직 AI 상담 데이터가 없어요."
                  />
                  <TodayStatCard
                    icon="👀"
                    label="AI 추천 클릭"
                    value={dashToday.recommendation_clicks}
                    unit="회"
                    emptyNote="AI 추천을 보고 우리 가게를 확인한 손님이 아직 없어요."
                  />
                  <TodayStatCard
                    icon="🎟"
                    label="쿠폰"
                    value={dashToday.coupons_issued}
                    unit="회"
                    emptyNote="아직 발급된 쿠폰이 없어요."
                  />
                  <TodayStatCard
                    icon="📅"
                    label="예약"
                    value={dashToday.reservations_created}
                    unit="건"
                    emptyNote="아직 들어온 예약이 없어요."
                  />
                </div>
              </section>

              {/* Section 2: 손님이 우리 가게를 만나는 과정 (핵심 Funnel) */}
              <section className="mb-8">
                <h2 className="mb-3 font-semibold">손님이 우리 가게를 만나는 과정</h2>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
                  <FunnelNode
                    icon="🤖"
                    title="AI가 손님을 만남"
                    value={`${dashToday.ai_interactions_total}회`}
                    isZero={dashToday.ai_interactions_total === 0}
                    emptyNote="아직 오늘 AI에게 직접 물어본 손님이 없어요."
                  />
                  <FunnelArrow />
                  <FunnelNode icon="⭐" title="우리 가게를 추천" caption="AI가 후보 중에서 우리 가게를 추천해요" />
                  <FunnelArrow />
                  <FunnelNode
                    icon="👀"
                    title="손님이 관심을 보임"
                    value={`${dashToday.recommendation_clicks}회`}
                    isZero={dashToday.recommendation_clicks === 0}
                    emptyNote="아직 추천을 보고 확인한 손님이 없어요."
                  />
                  <FunnelArrow />
                  <FunnelNode
                    icon="🎟"
                    title="쿠폰 / 예약"
                    value={`쿠폰 ${dashToday.coupons_issued}회 · 예약 ${dashToday.reservations_created}건`}
                    isZero={dashToday.coupons_issued === 0 && dashToday.reservations_created === 0}
                    emptyNote="아직 쿠폰이나 예약으로 이어진 손님이 없어요."
                  />
                  <FunnelArrow />
                  <FunnelNode
                    icon="🚶"
                    title="실제 방문"
                    value={`${dashToday.visits_confirmed}건`}
                    isZero={dashToday.visits_confirmed === 0}
                    emptyNote="아직 방문이 확인되지 않았어요."
                  />
                  <FunnelArrow />
                  <FunnelNode
                    icon="💰"
                    title="AI와 연결된 매출"
                    value={formatWon(dashToday.revenue.ai_connected_revenue)}
                    isZero={Number(dashToday.revenue.ai_connected_revenue) === 0}
                    emptyNote="아직 기록된 매출이 없어요. 예약이나 쿠폰 사용이 확인되면 여기 표시돼요."
                  />
                </div>
              </section>

              {/* Section 3: 오늘의 한마디 */}
              <section className="mb-8 rounded-md bg-gray-50 p-4 text-sm">
                <h2 className="mb-2 font-semibold">오늘의 한마디</h2>
                {dashToday.recommendation_clicks > 0 ? (
                  <p>오늘 AI 추천을 통해 {dashToday.recommendation_clicks}회 우리 가게를 확인했어요.</p>
                ) : (
                  <p className="text-gray-500">아직 충분한 데이터가 쌓이지 않았어요.</p>
                )}
              </section>

              {/* Section 4: 지금 사장님이 할 일 */}
              {(() => {
                const todo = buildTodo({
                  ownerProfile,
                  couponsCount: coupons.length,
                  reservationsEverCount: dashAll.reservations_created,
                  clicksToday: dashToday.recommendation_clicks,
                  couponsIssuedToday: dashToday.coupons_issued,
                  businessId: business.id,
                });
                return (
                  <section className="mb-8 rounded-md border border-gray-200 p-4 text-sm">
                    <h2 className="mb-2 font-semibold">💡 지금 사장님이 할 일</h2>
                    <p className="font-medium">{todo.message}</p>
                    <p className="mt-1 text-gray-600">{todo.detail}</p>
                    {todo.actionHref && todo.actionLabel && (
                      <Link
                        href={todo.actionHref}
                        className="mt-3 inline-block rounded-md bg-black px-4 py-2 text-white"
                      >
                        {todo.actionLabel}
                      </Link>
                    )}
                  </section>
                );
              })()}

              {/* Section 5: 우리 가게 성과 */}
              <section className="mb-8 rounded-md border border-gray-200 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="font-semibold">우리 가게 성과</h2>
                  <Link href={`/businesses/${business.id}/performance`} className="text-xs underline">
                    자세히 보기 →
                  </Link>
                </div>
                <p className="mb-3 text-xs text-gray-500">{performance.period} 기준</p>
                <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  <div className="rounded-md bg-gray-50 p-3">
                    <dt className="text-xs text-gray-500">전체 매출</dt>
                    <dd className="font-semibold">{formatWon(performance.revenue_total)}</dd>
                  </div>
                  <div className="rounded-md bg-gray-50 p-3">
                    <dt className="text-xs text-gray-500">AI와 연결된 매출</dt>
                    <dd className="font-semibold">{formatWon(performance.revenue_ai_connected)}</dd>
                  </div>
                  <div className="rounded-md bg-gray-50 p-3">
                    <dt className="text-xs text-gray-500">AI 상담</dt>
                    <dd className="font-semibold">{performance.ai_response_count.toLocaleString()}건</dd>
                  </div>
                </dl>
              </section>

              {/* Section 6/7: 더 많은 정보를 보고 싶다면 */}
              <section>
                <h2 className="mb-3 font-semibold">더 많은 정보를 보고 싶다면</h2>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {QUICK_LINKS(business.id).map((l) => (
                    <Link
                      key={l.label}
                      href={l.href}
                      className="rounded-md border border-gray-200 p-3 text-center text-sm hover:border-black"
                    >
                      {l.label}
                    </Link>
                  ))}
                </div>
              </section>
            </>
          )}
        </>
      )}
    </main>
  );
}
