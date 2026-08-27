"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FunnelArrow, FunnelNode } from "@/components/Funnel";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  ApiError,
  CATEGORY_LABELS,
  type Business,
  type BusinessOwnerProfile,
  type BusinessPilotDashboard,
  type Coupon,
  type IncomingPartnerInvite,
  type Menu,
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

// ---- 지금 사장님이 할 일 ----
interface TodoItem {
  message: string;
  detail: string;
  actionLabel?: string;
  actionHref?: string;
}

function buildTodo(params: {
  ownerProfile: BusinessOwnerProfile;
  incomingInviteCount: number;
  menusCount: number;
  couponsCount: number;
  reservationsEverCount: number;
  clicksToday: number;
  couponsIssuedToday: number;
  businessId: string;
}): TodoItem {
  const {
    ownerProfile,
    incomingInviteCount,
    menusCount,
    couponsCount,
    reservationsEverCount,
    clicksToday,
    couponsIssuedToday,
    businessId,
  } = params;

  const profileIncomplete = !ownerProfile.description || !textOf(ownerProfile.opening_hours);
  if (profileIncomplete) {
    return {
      message: "AI가 손님에게 답할 정보가 아직 부족해요.",
      detail: "가게 소개나 영업시간이 비어 있으면 AI가 \"확인이 필요합니다\"라고만 답해요.",
      actionLabel: "가게 정보 채우기",
      actionHref: `/businesses/${businessId}/profile`,
    };
  }

  if (incomingInviteCount > 0) {
    return {
      message: `주변 가게에서 받은 제휴 제안이 ${incomingInviteCount}건 있어요.`,
      detail: "수락하면 서로의 손님에게 AI가 자연스럽게 서로를 추천해줘요.",
      actionLabel: "제휴 제안 확인하기",
      actionHref: `/businesses/${businessId}/expansion`,
    };
  }

  if (menusCount === 0) {
    return {
      message: "아직 등록된 메뉴가 없어요.",
      detail: "메뉴가 있어야 AI가 손님에게 우리 가게 메뉴를 추천할 수 있어요.",
      actionLabel: "메뉴 등록하기",
      actionHref: `/businesses/${businessId}/menus`,
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
  { label: "메뉴 관리", href: `/businesses/${id}/menus` },
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
  const [incomingInvites, setIncomingInvites] = useState<IncomingPartnerInvite[] | null>(null);
  const [menus, setMenus] = useState<Menu[] | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [togglingStatus, setTogglingStatus] = useState(false);

  const [editingIdentity, setEditingIdentity] = useState(false);
  const [editNameKo, setEditNameKo] = useState("");
  const [editAddress, setEditAddress] = useState("");
  const [editCategory, setEditCategory] = useState<Business["category"] | "">("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

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
    setIncomingInvites(null);
    setMenus(null);
    Promise.all([
      api.getBusinessPilotDashboard(token, selectedId, "today"),
      api.getBusinessPilotDashboard(token, selectedId, "all"),
      api.getPerformance(token, selectedId),
      api.getOwnerProfile(token, selectedId),
      api.listCoupons(selectedId, token),
      // 받은 제휴 제안 - Expansion 화면에 들어가지 않으면 존재 자체를 알 방법이
      // 없었던 P1-4의 핵심 단절 지점이라 Home에서 반드시 가져온다. 실패해도
      // Home 전체가 막히지 않도록 조용히 빈 배열로 대체.
      api.listIncomingExpansionInvites(token, selectedId).catch(() => []),
      // P1-5 - claim된 업체 중 40%가 메뉴를 하나도 등록하지 않아 Customer AI가
      // 추천할 근거 자체가 없는 상태라, Home에서 메뉴 개수를 반드시 가져온다.
      api.listMenus(selectedId).catch(() => []),
    ])
      .then(([today, all, perf, profile, couponList, invites, menuList]) => {
        setDashToday(today);
        setDashAll(all);
        setPerformance(perf);
        setOwnerProfile(profile);
        setCoupons(couponList);
        setIncomingInvites(invites);
        setMenus(menuList);
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

  const onStartEditIdentity = () => {
    if (!business) return;
    setEditingIdentity(true);
    setEditNameKo(business.name_ko);
    setEditAddress(business.address);
    setEditCategory(business.category);
    setEditError(null);
  };

  const onSaveIdentity = async () => {
    if (!token || !business || !editCategory) return;
    setEditError(null);
    setEditSaving(true);
    try {
      const updated = await api.updateBusiness(token, business.id, {
        name_ko: editNameKo,
        address: editAddress,
        category: editCategory,
      });
      setBusinesses((prev) => prev?.map((b) => (b.id === updated.id ? updated : b)) ?? null);
      setEditingIdentity(false);
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setEditSaving(false);
    }
  };

  if (authLoading || !user) return null;

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">영종 AI</h1>
          <p className="mt-1 text-sm text-gray-600">
            영종 AI는 손님에게 우리 가게를 알리고, 관심을 예약·쿠폰으로 연결해 방문과 매출까지 도와드려요.
          </p>
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
            <div className="mb-6 rounded-md border border-gray-200 p-3 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold">{business.name_ko}</span>{" "}
                  <span className="text-gray-500">· {STATUS_LABEL[business.status]}</span>
                </div>
                <div className="flex items-center gap-2">
                  {!editingIdentity && (
                    <button onClick={onStartEditIdentity} className="text-gray-500 underline">
                      수정
                    </button>
                  )}
                  <button
                    onClick={toggleStatus}
                    disabled={togglingStatus}
                    className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
                  >
                    {business.status === "ACTIVE" ? "비공개로 전환" : "공개하기"}
                  </button>
                </div>
              </div>

              {editingIdentity && (
                <div className="mt-3 flex flex-col gap-2 border-t border-gray-200 pt-3">
                  <label className="flex flex-col gap-1 text-xs">
                    이름
                    <input
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                      value={editNameKo}
                      onChange={(e) => setEditNameKo(e.target.value)}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-xs">
                    주소
                    <input
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                      value={editAddress}
                      onChange={(e) => setEditAddress(e.target.value)}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-xs">
                    업종
                    <select
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                      value={editCategory}
                      onChange={(e) => setEditCategory(e.target.value as Business["category"])}
                    >
                      {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {editError && <p className="text-xs text-red-600">{editError}</p>}
                  <div className="mt-1 flex gap-2">
                    <button
                      onClick={onSaveIdentity}
                      disabled={editSaving || !editNameKo.trim() || !editAddress.trim()}
                      className="rounded-md bg-black px-3 py-1.5 text-xs text-white disabled:opacity-50"
                    >
                      {editSaving ? "저장 중..." : "저장"}
                    </button>
                    <button
                      onClick={() => setEditingIdentity(false)}
                      className="rounded-md border border-gray-300 px-3 py-1.5 text-xs"
                    >
                      취소
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {detailError && <p className="mb-4 text-sm text-red-600">{detailError}</p>}

          {!dashToday ||
          !dashAll ||
          !performance ||
          !ownerProfile ||
          coupons === null ||
          incomingInvites === null ||
          menus === null ||
          !business ? (
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

              {/* 핵심 Funnel: AI가 손님을 만나는 과정 */}
              {(() => {
                const allZero =
                  dashToday.ai_interactions_total === 0 &&
                  dashToday.recommendation_clicks === 0 &&
                  dashToday.coupons_issued === 0 &&
                  dashToday.reservations_created === 0;
                return (
                  <section className="mb-8">
                    <h2 className="mb-3 font-semibold">AI가 손님을 만나는 과정</h2>
                    {allZero && (
                      <p className="mb-3 text-sm text-gray-600">
                        영종 AI가 손님을 기다리고 있어요. 첫 번째 관심이 생기면 이곳에서 바로 보여드릴게요.
                      </p>
                    )}
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
                      <FunnelNode
                        icon="🤖"
                        title="AI와 나눈 대화"
                        value={`${dashToday.ai_interactions_total}회`}
                        caption="손님과 사장님이 AI와 나눈 대화 횟수예요."
                      />
                      <FunnelArrow />
                      <FunnelNode
                        icon="⭐"
                        title="우리 가게를 추천"
                        caption="AI가 손님에게 우리 가게를 추천해요. 추천 횟수는 정확하게 집계하지 않아요."
                      />
                      <FunnelArrow />
                      <FunnelNode
                        icon="👀"
                        title="관심을 보임"
                        value={`${dashToday.recommendation_clicks}회`}
                        caption="손님이 추천을 보고 눌러본 횟수예요."
                      />
                      <FunnelArrow />
                      <FunnelNode
                        icon="🎟"
                        title="쿠폰 / 예약"
                        value={`쿠폰 ${dashToday.coupons_issued}건 · 예약 ${dashToday.reservations_created}건`}
                        isZero={dashToday.coupons_issued === 0 && dashToday.reservations_created === 0}
                        emptyNote="아직 쿠폰이나 예약으로 이어진 손님이 없어요."
                      />
                      <FunnelArrow />
                      <FunnelNode
                        icon="🚶"
                        title="방문"
                        value={`${dashToday.visits_confirmed}건`}
                        isZero={dashToday.visits_confirmed === 0}
                        emptyNote="아직 방문이 확인되지 않았어요."
                      />
                      <FunnelArrow />
                      <FunnelNode
                        icon="💰"
                        title="AI를 통해 연결된 매출"
                        period="오늘"
                        value={formatWon(dashToday.revenue.ai_connected_revenue)}
                        isZero={Number(dashToday.revenue.ai_connected_revenue) === 0}
                        emptyNote="아직 기록된 매출이 없어요. 예약이나 쿠폰 사용이 확인되면 여기 표시돼요."
                      />
                    </div>
                  </section>
                );
              })()}

              {/* 지금 사장님이 할 일 */}
              {(() => {
                const todo = buildTodo({
                  ownerProfile,
                  incomingInviteCount: incomingInvites.length,
                  menusCount: menus.length,
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

              {/* 오늘 AI 활동 상세 (Funnel 요약, 큰 카드로 반복하지 않음) */}
              <section className="mb-8 rounded-md border border-gray-200 p-4">
                <h2 className="mb-2 font-semibold">오늘 AI 활동 상세</h2>
                <p className="text-sm text-gray-700">
                  상담 {dashToday.ai_interactions_total}회 · 추천 클릭 {dashToday.recommendation_clicks}회 · 쿠폰{" "}
                  {dashToday.coupons_issued}건 · 예약 {dashToday.reservations_created}건
                </p>
              </section>

              {/* 우리 가게 성과 (이번 달) */}
              <section className="mb-8 rounded-md border border-gray-200 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="font-semibold">우리 가게 성과</h2>
                  <Link href={`/businesses/${business.id}/performance`} className="text-sm underline">
                    자세히 보기 →
                  </Link>
                </div>
                <p className="mb-3 text-sm text-gray-500">이번 달 기준</p>
                <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  <div className="rounded-md bg-gray-50 p-3">
                    <dt className="text-sm text-gray-500">우리 가게 전체 매출</dt>
                    <dd className="font-semibold">{formatWon(performance.revenue_total)}</dd>
                  </div>
                  <div className="rounded-md bg-gray-50 p-3">
                    <dt className="text-sm text-gray-500">AI를 통해 연결된 매출</dt>
                    <dd className="font-semibold">{formatWon(performance.revenue_ai_connected)}</dd>
                  </div>
                  <div className="rounded-md bg-gray-50 p-3">
                    <dt className="text-sm text-gray-500">AI 상담</dt>
                    <dd className="font-semibold">{performance.ai_response_count.toLocaleString()}건</dd>
                  </div>
                </dl>
              </section>

              {/* 더 많은 정보를 보고 싶다면 */}
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
