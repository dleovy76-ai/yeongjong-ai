"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  ApiError,
  PILOT_PERIOD_LABELS,
  type BusinessPilotDashboard,
  type PilotPeriod,
} from "@/lib/api";

const PERIODS: PilotPeriod[] = ["today", "yesterday", "7d", "30d", "all"];

const AGENT_LABELS: Record<string, string> = {
  manager: "Manager AI",
  customer: "Customer AI",
  chef: "Chef AI",
  info: "Info AI",
  expansion: "Expansion AI",
};

function formatWon(amount: string): string {
  return `${Number(amount).toLocaleString()}원`;
}

export default function BusinessPilotDashboardPage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();

  const [period, setPeriod] = useState<PilotPeriod>("30d");
  const [dashboard, setDashboard] = useState<BusinessPilotDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    setError(null);
    api
      .getBusinessPilotDashboard(token, id, period)
      .then(setDashboard)
      .catch((err) => setError(err instanceof ApiError ? err.message : "불러오기 실패"))
      .finally(() => setLoading(false));
  }, [token, id, period]);

  useEffect(() => {
    load();
  }, [load]);

  if (authLoading || !token) return null;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">파일럿 운영 현황</h1>
      <p className="mb-6 text-sm text-gray-600">
        {dashboard ? dashboard.business_name : "우리 가게"}에서 AI가 실제로 얼마나 쓰이고 매출로 이어졌는지 봅니다.
      </p>

      <div className="mb-8 flex flex-wrap gap-2">
        {PERIODS.map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`rounded-full border px-4 py-1.5 text-sm ${
              period === p ? "border-black bg-black text-white" : "border-gray-300 text-gray-600"
            }`}
          >
            {PILOT_PERIOD_LABELS[p]}
          </button>
        ))}
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
      {loading && !dashboard && <p className="text-gray-500">불러오는 중...</p>}

      {dashboard && (
        <>
          <section className="mb-10">
            <h2 className="mb-3 font-semibold">손님이 줄어드는 단계</h2>
            <div className="flex flex-col gap-2">
              {dashboard.funnel.map((step) => (
                <div key={step.key} className="flex items-center justify-between rounded-md border border-gray-200 p-3 text-sm">
                  <span>{step.label}</span>
                  <span className="flex items-center gap-3">
                    <span className="font-semibold tabular-nums">{step.count.toLocaleString()}</span>
                    {step.conversion_rate_from_previous !== null && (
                      <span className="text-xs text-gray-400">
                        (이전 단계 대비 {(step.conversion_rate_from_previous * 100).toFixed(1)}%)
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="mb-10">
            <h2 className="mb-3 font-semibold">매출</h2>
            <div className="rounded-md border-2 border-black p-4">
              <p className="text-xs text-gray-500">AI 추천으로 이어진 매출 (쿠폰·예약으로 확인된 것만)</p>
              <p className="text-2xl font-bold">{formatWon(dashboard.revenue.ai_connected_revenue)}</p>
              <p className="mt-1 text-xs text-gray-400">
                {dashboard.revenue.ai_connected_transaction_count.toLocaleString()}건
              </p>
            </div>
            <dl className="mt-3 grid grid-cols-3 gap-3 text-sm">
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-xs text-gray-500">쿠폰으로 확인</dt>
                <dd className="font-semibold">{formatWon(dashboard.revenue.direct_revenue)}</dd>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-xs text-gray-500">예약으로 확인</dt>
                <dd className="font-semibold">{formatWon(dashboard.revenue.assisted_revenue)}</dd>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-xs text-gray-500">연결 확인 안 됨 (AI 매출 아님)</dt>
                <dd className="font-semibold">{formatWon(dashboard.revenue.unknown_revenue)}</dd>
              </div>
            </dl>
            <p className="mt-2 text-xs text-gray-400">
              전체 거래액 {formatWon(dashboard.revenue.total_revenue)} 중, 실제로 AI 추천→쿠폰/예약으로 이어진 것만
              "AI 연결 매출"로 표시합니다. 연결이 확인되지 않은 거래는 AI 매출로 세지 않습니다.
            </p>
          </section>

          <section className="mb-10">
            <h2 className="mb-3 font-semibold">AI 직원별 성과</h2>
            <div className="flex flex-col gap-3">
              {dashboard.agents.map((agent) => (
                <div key={agent.agent_type} className="rounded-md border border-gray-200 p-3 text-sm">
                  <p className="font-semibold">{AGENT_LABELS[agent.agent_type] ?? agent.agent_type}</p>
                  {agent.interactions !== null && (
                    <p className="text-gray-600">응대: {agent.interactions.toLocaleString()}건</p>
                  )}
                  {agent.recommendation_clicks !== null && (
                    <p className="text-gray-600">추천 클릭: {agent.recommendation_clicks.toLocaleString()}건</p>
                  )}
                  {agent.note && <p className="mt-1 text-xs text-gray-400">{agent.note}</p>}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-3 font-semibold">쿠폰 · 예약</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-xs text-gray-500">쿠폰 발급</dt>
                <dd className="font-semibold">{dashboard.coupons_issued.toLocaleString()}</dd>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-xs text-gray-500">쿠폰 사용</dt>
                <dd className="font-semibold">{dashboard.coupons_redeemed.toLocaleString()}</dd>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-xs text-gray-500">예약 생성</dt>
                <dd className="font-semibold">{dashboard.reservations_created.toLocaleString()}</dd>
              </div>
              <div className="rounded-md bg-gray-50 p-3">
                <dt className="text-xs text-gray-500">예약 완료</dt>
                <dd className="font-semibold">{dashboard.reservations_completed.toLocaleString()}</dd>
              </div>
            </dl>
          </section>
        </>
      )}
    </main>
  );
}
