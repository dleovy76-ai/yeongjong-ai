"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type Performance } from "@/lib/api";

const AGENT_TYPE_LABEL: Record<string, string> = {
  customer: "고객 응대",
  chef: "메뉴 추천",
  info: "관광객 추천",
  manager: "매니저 상담",
  expansion: "연관업체 분석",
  referral_message: "제휴 메시지 작성",
  profile_draft: "소개글 초안 작성",
};

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-gray-200 p-4 text-center">
      <p className="text-2xl font-bold">{value}</p>
      <p className="mt-1 text-sm text-gray-500">{label}</p>
    </div>
  );
}

function topAgentType(counts: Record<string, number>): { label: string; count: number } | null {
  const entries = Object.entries(counts);
  if (entries.length === 0) return null;
  const [type, count] = entries.reduce((a, b) => (b[1] > a[1] ? b : a));
  return { label: AGENT_TYPE_LABEL[type] ?? type, count };
}

function formatMinutesAsHours(minutes: number): string {
  if (minutes < 60) return `${minutes}분`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}시간` : `${hours}시간 ${rest}분`;
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
          <div className="mb-8 rounded-md bg-gray-50 p-4 text-sm">
            <p>
              사장님, 이번 달 AI가 고객 문의 {performance.ai_response_count.toLocaleString()}건을
              처리했습니다.
            </p>
            {(() => {
              const top = topAgentType(performance.ai_response_count_by_agent_type);
              return top ? (
                <p className="mt-1">
                  가장 많이 활용된 기능은 <strong>{top.label}</strong>입니다 ({top.count}건 · 사용량
                  기준, 매출 인과관계까지 증명된 값은 아니에요).
                </p>
              ) : null;
            })()}
          </div>

          <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatCard label="매출" value={`${Number(performance.revenue_total).toLocaleString()}원`} />
            <StatCard
              label="AI 연결 거래액"
              value={`${Number(performance.revenue_ai_connected).toLocaleString()}원`}
            />
            <StatCard label="AI 응대" value={`${performance.ai_response_count.toLocaleString()}건`} />
            <StatCard label="예약" value={`${performance.reservations_this_month.toLocaleString()}건`} />
            <StatCard label="쿠폰 사용" value={`${performance.coupons_redeemed.toLocaleString()}건`} />
            <StatCard
              label="예상 절감시간"
              value={formatMinutesAsHours(performance.estimated_time_saved_minutes)}
            />
          </div>

          <div className="mb-8 grid grid-cols-3 gap-3">
            <StatCard label="DIRECT (쿠폰)" value={`${Number(performance.revenue_direct).toLocaleString()}원`} />
            <StatCard label="ASSISTED (예약)" value={`${Number(performance.revenue_assisted).toLocaleString()}원`} />
            <StatCard label="UNKNOWN (연결 불명)" value={`${Number(performance.revenue_unknown).toLocaleString()}원`} />
          </div>
          <p className="mb-8 -mt-4 text-xs text-gray-500">{performance.revenue_ai_connected_note}</p>

          <div className="mb-8 rounded-md border border-gray-200 p-4 text-sm">
            <p className="font-semibold">
              내 추천으로 실제 가입한 업체: {performance.successful_referrals.toLocaleString()}곳
            </p>
            <p className="mt-1 text-gray-500">{performance.successful_referrals_note}</p>
            <Link href={`/businesses/${id}/expansion`} className="mt-2 inline-block text-xs underline">
              초대 링크 보내러 가기 →
            </Link>
          </div>

          <div className="rounded-md border border-gray-200 p-4 text-sm text-gray-500">
            {performance.estimated_time_saved_note}
          </div>
        </>
      )}
    </main>
  );
}
