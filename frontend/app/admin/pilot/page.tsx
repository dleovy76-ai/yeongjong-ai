"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  ApiError,
  PILOT_PERIOD_LABELS,
  PILOT_STATUS_LABELS,
  type AdminPilotOverview,
  type PilotPeriod,
  type PilotStatus,
} from "@/lib/api";

const PERIODS: PilotPeriod[] = ["today", "yesterday", "7d", "30d", "all"];
const PILOT_STATUSES: PilotStatus[] = ["PILOT_ACTIVE", "PILOT_PAUSED", "PILOT_COMPLETED"];

function formatWon(amount: string): string {
  return `${Number(amount).toLocaleString()}원`;
}

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md bg-gray-50 p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export default function AdminPilotDashboardPage() {
  const { token, user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [period, setPeriod] = useState<PilotPeriod>("30d");
  const [overview, setOverview] = useState<AdminPilotOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  const load = useCallback(() => {
    if (!token) return;
    setLoading(true);
    setError(null);
    api
      .getAdminPilotOverview(token, period)
      .then(setOverview)
      .catch((err) => setError(err instanceof ApiError ? err.message : "불러오기 실패"))
      .finally(() => setLoading(false));
  }, [token, period]);

  useEffect(() => {
    load();
  }, [load]);

  const onChangePilotStatus = async (businessId: string, pilotStatus: PilotStatus | null) => {
    if (!token) return;
    setUpdatingId(businessId);
    try {
      await api.updatePilotStatus(token, businessId, pilotStatus);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "파일럿 상태 변경 실패");
    } finally {
      setUpdatingId(null);
    }
  };

  const onExport = async () => {
    if (!token) return;
    setExporting(true);
    try {
      await api.downloadPilotCsv(token, period);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "CSV 다운로드 실패");
    } finally {
      setExporting(false);
    }
  };

  if (authLoading || !user) return null;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-2xl font-bold">파일럿 운영 현황</h1>
        <Link href="/admin" className="text-sm underline">
          ← 관리자 메인
        </Link>
      </div>
      <p className="mb-6 text-sm text-gray-600">
        "AI가 실제로 지역 업체의 매출을 만드는가?"를 측정합니다. 파일럿 상태로 지정된 업체만 집계합니다.
      </p>

      <div className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
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
        <button
          onClick={onExport}
          disabled={exporting || !overview || overview.businesses.length === 0}
          className="rounded-md border border-black px-4 py-1.5 text-sm disabled:opacity-50"
        >
          {exporting ? "다운로드 중..." : "CSV 다운로드"}
        </button>
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
      {loading && !overview && <p className="text-gray-500">불러오는 중...</p>}

      {overview && overview.pilot_business_count === 0 && (
        <p className="rounded-md border border-gray-200 p-4 text-sm text-gray-500">
          아직 파일럿 상태로 지정된 업체가 없습니다. 아래 업체 목록에서 "파일럿 진행 중"으로 지정하면 여기 집계됩니다.
        </p>
      )}

      {overview && overview.pilot_business_count > 0 && (
        <>
          <section className="mb-10">
            <h2 className="mb-3 font-semibold">손님이 줄어드는 단계</h2>
            <div className="flex flex-col gap-2">
              {overview.funnel.map((step) => (
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

          <section className="mb-10 rounded-md border-2 border-black p-4">
            <p className="text-xs text-gray-500">AI 추천으로 이어진 매출 (쿠폰·예약으로 확인된 것만, 파일럿 업체 전체)</p>
            <p className="text-2xl font-bold">{formatWon(overview.revenue.ai_connected_revenue)}</p>
            <p className="mt-1 text-xs text-gray-400">
              전체 거래액 {formatWon(overview.revenue.total_revenue)} · 연결 확인 안 됨(AI 매출 아님){" "}
              {formatWon(overview.revenue.unknown_revenue)}
            </p>
          </section>

          <section className="mb-10">
            <h2 className="mb-3 font-semibold">업체 현황</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <KpiCard label="파일럿 업체 수" value={overview.pilot_business_count} />
              <KpiCard label="공개 중인 업체 수" value={overview.active_business_count} />
              <KpiCard label="오늘 AI 쓴 업체" value={overview.daily_active_businesses} />
              <KpiCard label="이번 주 AI 쓴 업체" value={overview.weekly_active_businesses} />
            </dl>
          </section>

          <section className="mb-10">
            <h2 className="mb-3 font-semibold">손님 응대</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <KpiCard label="Customer AI 질문" value={overview.customer_ai_questions} />
              <KpiCard label="Chef AI 질문" value={overview.chef_ai_questions} />
              <KpiCard label="Info AI 질문 (전체 합산)" value={overview.info_ai_questions} />
              <KpiCard label="AI가 추천한 횟수 (전체 합산)" value={overview.recommendation_impressions} />
              <KpiCard label="손님이 실제로 눌러본 횟수 (전체 합산)" value={overview.recommendation_clicks} />
            </dl>
            <p className="mt-2 text-xs text-gray-400">
              Info AI는 특정 업체에 매이지 않는 AI라 질문·추천 수는 업체별이 아니라 전체 합산 값입니다.
            </p>
          </section>

          <section className="mb-10">
            <h2 className="mb-3 font-semibold">실제 행동으로 이어진 수</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <KpiCard label="쿠폰 발급" value={overview.coupons_issued} />
              <KpiCard label="쿠폰 사용" value={overview.coupons_redeemed} />
              <KpiCard label="예약 생성" value={overview.reservations_created} />
              <KpiCard label="예약 완료" value={overview.reservations_completed} />
              <KpiCard label="방문 확인" value={overview.visits_confirmed} />
              <KpiCard label="거래 생성" value={overview.transactions_created} />
            </dl>
          </section>

          <section className="mb-10">
            <h2 className="mb-3 font-semibold">업체 확장</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <KpiCard label="Expansion AI 실행" value={overview.expansion_runs} />
              <KpiCard label="추천 파트너 후보" value={overview.partner_candidates} />
              <KpiCard label="제휴 제안" value={overview.partner_invites} />
              <KpiCard label="소개 링크 클릭" value={overview.referral_clicks} />
              <KpiCard label="소개로 새로 가입한 업체" value={overview.new_businesses_via_referral} />
            </dl>
          </section>

          <section>
            <h2 className="mb-3 font-semibold">업체별 비교</h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-gray-300 text-left text-xs text-gray-500">
                    <th className="py-2 pr-3">업체</th>
                    <th className="py-2 pr-3">AI 사용</th>
                    <th className="py-2 pr-3">추천 클릭</th>
                    <th className="py-2 pr-3">거래</th>
                    <th className="py-2 pr-3">AI 연결 매출</th>
                    <th className="py-2 pr-3">파일럿 상태</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.businesses.map((b) => (
                    <tr key={b.business_id} className="border-b border-gray-100">
                      <td className="py-2 pr-3 font-medium">
                        <Link href={`/businesses/${b.business_id}/pilot`} className="underline">
                          {b.business_name}
                        </Link>
                      </td>
                      <td className="py-2 pr-3 tabular-nums">{b.ai_interactions.toLocaleString()}</td>
                      <td className="py-2 pr-3 tabular-nums">{b.recommendation_clicks.toLocaleString()}</td>
                      <td className="py-2 pr-3 tabular-nums">{b.transactions.toLocaleString()}</td>
                      <td className="py-2 pr-3 tabular-nums font-semibold">{formatWon(b.ai_connected_revenue)}</td>
                      <td className="py-2 pr-3">
                        <select
                          value={b.pilot_status ?? ""}
                          disabled={updatingId === b.business_id}
                          onChange={(e) =>
                            onChangePilotStatus(b.business_id, (e.target.value || null) as PilotStatus | null)
                          }
                          className="rounded-md border border-gray-300 px-2 py-1 text-xs"
                        >
                          {PILOT_STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {PILOT_STATUS_LABELS[s]}
                            </option>
                          ))}
                          <option value="">파일럿 제외</option>
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
