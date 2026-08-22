"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type Reservation, type ReservationStatus } from "@/lib/api";

const STATUS_LABEL: Record<ReservationStatus, string> = {
  REQUESTED: "요청됨",
  CONFIRMED: "확정됨",
  CANCELLED: "취소됨",
  COMPLETED: "방문 완료",
  NO_SHOW: "노쇼",
};

const NEXT_ACTIONS: Record<ReservationStatus, { label: string; status: ReservationStatus }[]> = {
  REQUESTED: [
    { label: "예약 확정", status: "CONFIRMED" },
    { label: "취소", status: "CANCELLED" },
  ],
  CONFIRMED: [
    { label: "방문 완료 처리", status: "COMPLETED" },
    { label: "노쇼 처리", status: "NO_SHOW" },
    { label: "취소", status: "CANCELLED" },
  ],
  CANCELLED: [],
  COMPLETED: [],
  NO_SHOW: [],
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("ko-KR", {
    month: "long",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ReservationsPage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();

  const [reservations, setReservations] = useState<Reservation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    api
      .listReservations(token, id)
      .then(setReservations)
      .catch((err) => setError(err instanceof ApiError ? err.message : "예약 목록을 불러오지 못했습니다."));
  }, [id, token]);

  const changeStatus = async (reservation: Reservation, status: ReservationStatus) => {
    if (!token) return;
    setError(null);
    setUpdatingId(reservation.id);
    try {
      const updated = await api.updateReservationStatus(token, id, reservation.id, status);
      setReservations((prev) => prev?.map((r) => (r.id === updated.id ? updated : r)) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "상태 변경 중 오류가 발생했습니다.");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <h1 className="mb-8 text-2xl font-bold">예약 관리</h1>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {reservations === null ? (
        <p className="text-gray-500">불러오는 중...</p>
      ) : reservations.length === 0 ? (
        <p className="text-gray-500">아직 들어온 예약이 없어요.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {reservations.map((reservation) => (
            <li key={reservation.id} className="rounded-md border border-gray-200 p-4 text-sm">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold">{formatDateTime(reservation.reservation_time)}</p>
                  <p className="text-gray-600">
                    {reservation.customer_name} · {reservation.customer_phone} · {reservation.party_size}명
                  </p>
                  {reservation.notes && <p className="mt-1 text-gray-500">{reservation.notes}</p>}
                </div>
                <span className="whitespace-nowrap rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-700">
                  {STATUS_LABEL[reservation.status]}
                </span>
              </div>
              {NEXT_ACTIONS[reservation.status].length > 0 && (
                <div className="mt-3 flex gap-2">
                  {NEXT_ACTIONS[reservation.status].map((action) => (
                    <button
                      key={action.status}
                      onClick={() => changeStatus(reservation, action.status)}
                      disabled={updatingId === reservation.id}
                      className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <Link href={`/businesses/${id}`} className="mt-8 inline-block text-sm underline">
        AI 미리보기로 돌아가기
      </Link>
    </main>
  );
}
