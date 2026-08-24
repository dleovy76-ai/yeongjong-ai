"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type Performance } from "@/lib/api";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-gray-200 p-4 text-center">
      <p className="text-2xl font-bold">{value}</p>
      <p className="mt-1 text-sm text-gray-500">{label}</p>
    </div>
  );
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
      <h1 className="mb-2 text-2xl font-bold">이번 달 성과</h1>
      {performance && <p className="mb-8 text-sm text-gray-500">{performance.period}</p>}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {!performance ? (
        <p className="text-gray-500">불러오는 중...</p>
      ) : (
        <>
          <div className="mb-8 grid grid-cols-3 gap-3">
            <StatCard label="AI 응대 건수" value={performance.ai_response_count} />
            <StatCard label="쿠폰 발급" value={performance.coupons_issued} />
            <StatCard label="쿠폰 사용" value={performance.coupons_redeemed} />
          </div>

          <div className="mb-3 grid grid-cols-2 gap-3">
            <StatCard label="이번 달 매출 기록" value={`${Number(performance.revenue_total).toLocaleString()}원`} />
            <StatCard
              label="AI 연결 매출"
              value={`${Number(performance.revenue_ai_connected).toLocaleString()}원`}
            />
          </div>
          <div className="mb-8 grid grid-cols-3 gap-3">
            <StatCard label="DIRECT (쿠폰)" value={`${Number(performance.revenue_direct).toLocaleString()}원`} />
            <StatCard label="ASSISTED (예약)" value={`${Number(performance.revenue_assisted).toLocaleString()}원`} />
            <StatCard label="UNKNOWN (연결 불명)" value={`${Number(performance.revenue_unknown).toLocaleString()}원`} />
          </div>
          <p className="mb-8 -mt-4 text-xs text-gray-500">{performance.revenue_ai_connected_note}</p>

          <div className="rounded-md border border-gray-200 p-4">
            <p className="text-lg font-semibold">
              예상 업무 절감: 약 {performance.estimated_time_saved_minutes}분
            </p>
            <p className="mt-1 text-sm text-gray-500">{performance.estimated_time_saved_note}</p>
          </div>
        </>
      )}
    </main>
  );
}
