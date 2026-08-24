"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, type MyHistory, ApiError } from "@/lib/api";

const COUPON_STATUS_LABEL: Record<string, string> = {
  ISSUED: "발급됨 (사용 전)",
  REDEEMED: "사용 완료",
};

const RESERVATION_STATUS_LABEL: Record<string, string> = {
  REQUESTED: "요청됨",
  CONFIRMED: "확정됨",
  CANCELLED: "취소됨",
  COMPLETED: "방문 완료",
  NO_SHOW: "노쇼",
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function MyHistoryPage() {
  const { token, user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [history, setHistory] = useState<MyHistory | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      router.push("/login");
      return;
    }
    api
      .getMyHistory(token)
      .then(setHistory)
      .catch((err) => setError(err instanceof ApiError ? err.message : "불러오기 실패"));
  }, [authLoading, token, router]);

  if (authLoading || !user) return null;

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">내 이력</h1>
      <p className="mb-8 text-sm text-gray-500">
        로그인한 뒤 받은 쿠폰과 예약만 여기 모입니다. 로그인 전에 받은 쿠폰/예약은 연결되지 않아요.
      </p>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {history === null ? (
        <p className="text-gray-500">불러오는 중...</p>
      ) : (
        <div className="flex flex-col gap-10">
          <section>
            <h2 className="mb-3 text-lg font-semibold">받은 쿠폰</h2>
            {history.coupons.length === 0 ? (
              <p className="text-sm text-gray-500">아직 받은 쿠폰이 없어요.</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {history.coupons.map((c) => (
                  <li key={c.id} className="rounded-md border border-gray-200 p-4">
                    <p className="font-semibold">
                      {c.business_name} · {c.coupon_title}
                    </p>
                    <p className="mt-1 text-sm text-gray-500">
                      코드 {c.code} · {COUPON_STATUS_LABEL[c.status] ?? c.status}
                    </p>
                    <p className="mt-1 text-xs text-gray-400">{formatDateTime(c.issued_at)} 발급</p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg font-semibold">예약 이력</h2>
            {history.reservations.length === 0 ? (
              <p className="text-sm text-gray-500">아직 요청한 예약이 없어요.</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {history.reservations.map((r) => (
                  <li key={r.id} className="rounded-md border border-gray-200 p-4">
                    <p className="font-semibold">{r.business_name}</p>
                    <p className="mt-1 text-sm text-gray-500">
                      {formatDateTime(r.reservation_time)} · {r.party_size}명 ·{" "}
                      {RESERVATION_STATUS_LABEL[r.status] ?? r.status}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
