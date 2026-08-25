"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { FunnelArrow, FunnelNode } from "@/components/Funnel";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type Performance } from "@/lib/api";

function formatWon(amount: string): string {
  return `${Number(amount).toLocaleString()}원`;
}

// performance.period는 항상 "YYYY-MM"(이번 달 1일 기준) 원본 문자열이라,
// 원본 그대로 노출하지 않고 사장님이 읽기 쉬운 날짜 범위로 바꾼다.
function formatMonthRange(period: string): string {
  const [yearStr, monthStr] = period.split("-");
  const year = Number(yearStr);
  const month = Number(monthStr);
  if (!year || !month) return period;
  const lastDay = new Date(year, month, 0).getDate();
  return `${year}년 ${month}월 1일 ~ ${month}월 ${lastDay}일`;
}

export default function PerformancePage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();

  const [performance, setPerformance] = useState<Performance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    api
      .getPerformance(token, id)
      .then(setPerformance)
      .catch((err) => setError(err instanceof ApiError ? err.message : "불러오기 실패"));
  }, [id, token]);

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">이번 달 우리 가게 성과</h1>
      <p className="mb-1 text-sm text-gray-600">
        AI가 손님에게 우리 가게를 알리고, 관심 → 예약/쿠폰 → 방문 → 매출까지 연결된 흐름을 보여드려요.
      </p>
      {performance && <p className="mb-8 text-sm text-gray-500">{formatMonthRange(performance.period)}</p>}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {!performance ? (
        <p className="text-gray-500">불러오는 중...</p>
      ) : (
        <>
          {/* 핵심 Funnel */}
          <section className="mb-8">
            <h2 className="mb-3 font-semibold">손님이 우리 가게를 만나는 과정</h2>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
              <FunnelNode
                icon="🤖"
                title="AI 상담"
                value={`${performance.ai_response_count}회`}
                caption="손님과 사장님이 AI와 나눈 대화 횟수예요."
              />
              <FunnelArrow />
              <FunnelNode
                icon="👀"
                title="우리 가게를 눌러본 횟수"
                value={`${performance.recommendation_clicks}회`}
                caption={performance.recommendation_clicks_note}
              />
              <FunnelArrow />
              <FunnelNode
                icon="🎟"
                title="쿠폰 / 예약"
                value={`쿠폰 ${performance.coupons_issued}건 · 예약 ${performance.reservations_this_month}건`}
                isZero={performance.coupons_issued === 0 && performance.reservations_this_month === 0}
                emptyNote="아직 쿠폰이나 예약으로 이어진 손님이 없어요."
              />
              <FunnelArrow />
              <FunnelNode
                icon="🚶"
                title="방문 확인"
                value={`${performance.visits_confirmed}건`}
                caption={performance.visits_confirmed_note}
                isZero={performance.visits_confirmed === 0}
                emptyNote="아직 방문이 확인되지 않았어요."
              />
              <FunnelArrow />
              <FunnelNode
                icon="💰"
                title="실제 매출"
                period="이번 달"
                value={formatWon(performance.revenue_total)}
                isZero={Number(performance.revenue_total) === 0}
                emptyNote="아직 기록된 매출이 없어요."
              />
            </div>
          </section>

          {/* 전체 매출 요약 */}
          <section className="mb-8 rounded-md border-2 border-black p-4">
            <p className="text-sm text-gray-500">이번 달 전체 매출</p>
            <p className="text-2xl font-bold">{formatWon(performance.revenue_total)}</p>
            {Number(performance.revenue_total) === 0 ? (
              <p className="mt-2 text-sm text-gray-600">
                아직 기록된 매출이 없어요. 첫 매출이 기록되면 여기에 바로 표시돼요.
              </p>
            ) : (
              <>
                <p className="mt-2 text-sm text-gray-500">└ 이 중 AI와 연결된 매출</p>
                <p className="text-lg font-semibold">{formatWon(performance.revenue_ai_connected)}</p>
                <p className="mt-1 text-sm text-gray-600">{performance.revenue_ai_connected_note}</p>
              </>
            )}
          </section>

          {/* 매출 상세 (쿠폰/예약/확인불가) */}
          <section className="mb-8">
            <h2 className="mb-3 font-semibold">매출 상세</h2>
            <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-sm text-gray-500">🎟 쿠폰으로 확인된 매출</dt>
                <dd className="font-semibold">{formatWon(performance.revenue_direct)}</dd>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-sm text-gray-500">📅 예약으로 확인된 매출</dt>
                <dd className="font-semibold">{formatWon(performance.revenue_assisted)}</dd>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-sm text-gray-500">🔎 연결 경로를 확인할 수 없는 매출</dt>
                <dd className="font-semibold">{formatWon(performance.revenue_unknown)}</dd>
              </div>
            </dl>
          </section>

          {/* AI 활동 */}
          <section className="mb-8 rounded-md border border-gray-200 p-4">
            <h2 className="mb-2 font-semibold">🤖 AI 활동</h2>
            <p className="text-sm text-gray-700">
              AI 상담 {performance.ai_response_count}회 · 예약 {performance.reservations_this_month}건 · 쿠폰 사용{" "}
              {performance.coupons_redeemed}건
            </p>
            <p className="mt-3 text-sm text-gray-500">예상 절감 시간</p>
            <p className="text-lg font-semibold">{performance.estimated_time_saved_minutes}분</p>
            <p className="mt-1 text-sm text-gray-600">{performance.estimated_time_saved_note}</p>
          </section>

          {/* 지금까지 소개로 가입한 업체 (전체 기간 - 이번 달 성과와 기간이 다름) */}
          <section className="rounded-md border border-gray-200 p-4 text-sm">
            <p className="font-semibold">🤝 지금까지 소개로 가입한 업체</p>
            <p className="mt-1 text-lg font-semibold">{performance.successful_referrals.toLocaleString()}곳</p>
            <p className="mt-1 text-gray-500">전체 기간 누적 · {performance.successful_referrals_note}</p>
          </section>
        </>
      )}
    </main>
  );
}
