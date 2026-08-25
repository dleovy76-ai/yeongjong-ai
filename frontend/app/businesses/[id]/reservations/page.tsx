"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type Reservation, type ReservationStatus, type Transaction } from "@/lib/api";

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

function formatWon(amount: string): string {
  return `${Number(amount).toLocaleString()}원`;
}

export default function ReservationsPage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();

  const [reservations, setReservations] = useState<Reservation[] | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const [openAmountFormId, setOpenAmountFormId] = useState<string | null>(null);
  const [amountInput, setAmountInput] = useState("");
  const [recordingTransaction, setRecordingTransaction] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [justRecordedId, setJustRecordedId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      api.listReservations(token, id),
      api.listTransactions(token, id).catch(() => []),
    ])
      .then(([r, t]) => {
        setReservations(r);
        setTransactions(t);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "예약 목록을 불러오지 못했습니다."));
  }, [id, token]);

  const transactionByReservationId = new Map(
    transactions.filter((t) => t.reservation_id).map((t) => [t.reservation_id as string, t])
  );

  const changeStatus = async (reservation: Reservation, status: ReservationStatus) => {
    if (!token) return;
    setError(null);
    setUpdatingId(reservation.id);
    try {
      const updated = await api.updateReservationStatus(token, id, reservation.id, status);
      setReservations((prev) => prev?.map((r) => (r.id === updated.id ? updated : r)) ?? null);
      if (status === "COMPLETED") {
        // 방문 완료 처리 직후 바로 매출 입력을 자연스럽게 이어서 보여준다 -
        // "Transaction을 생성하세요" 대신 "실제 결제금액을 기록해주세요"로.
        setOpenAmountFormId(reservation.id);
        setAmountInput("");
        setTransactionError(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "상태 변경 중 오류가 발생했습니다.");
    } finally {
      setUpdatingId(null);
    }
  };

  const onRecordTransaction = async (reservationId: string) => {
    if (!token) return;
    const amount = Number(amountInput);
    if (!amountInput || amount <= 0) return;
    setRecordingTransaction(true);
    setTransactionError(null);
    try {
      const transaction = await api.createTransaction(token, id, {
        amount: amountInput,
        reservation_id: reservationId,
      });
      setTransactions((prev) => [...prev, transaction]);
      setOpenAmountFormId(null);
      setAmountInput("");
      setJustRecordedId(reservationId);
    } catch (err) {
      setTransactionError(err instanceof ApiError ? err.message : "매출 기록 중 오류가 발생했습니다.");
    } finally {
      setRecordingTransaction(false);
    }
  };

  const onSkipForNow = () => {
    setOpenAmountFormId(null);
    setAmountInput("");
    setTransactionError(null);
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
                <span className="whitespace-nowrap rounded-full bg-gray-100 px-2 py-1 text-sm text-gray-700">
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

              {reservation.status === "COMPLETED" &&
                (() => {
                  const transaction = transactionByReservationId.get(reservation.id);

                  if (transaction) {
                    return (
                      <div className="mt-3 border-t border-gray-100 pt-3">
                        <p className="text-gray-700">
                          실제 매출 <span className="font-semibold">{formatWon(transaction.amount)}</span>
                        </p>
                        {justRecordedId === reservation.id && (
                          <p className="mt-1 text-green-700">
                            매출이 기록됐어요. 예약을 통해 방문한 손님의 매출로 연결됐어요.
                          </p>
                        )}
                      </div>
                    );
                  }

                  if (openAmountFormId === reservation.id) {
                    return (
                      <div className="mt-3 rounded-md bg-gray-50 p-3">
                        <p className="font-semibold">🎉 방문이 확인됐어요</p>
                        <p className="mt-1 text-gray-600">
                          실제 결제금액을 기록하면 AI를 통해 연결된 매출로 확인할 수 있어요.
                        </p>
                        <div className="mt-2 flex items-center gap-2">
                          <span className="text-lg font-semibold">₩</span>
                          <input
                            type="number"
                            min="1"
                            inputMode="numeric"
                            autoFocus
                            placeholder="50000"
                            className="w-32 rounded-md border border-gray-300 px-3 py-2 text-base"
                            value={amountInput}
                            onChange={(e) => setAmountInput(e.target.value)}
                          />
                        </div>
                        {amountInput && Number(amountInput) > 0 && (
                          <p className="mt-1 text-gray-500">{Number(amountInput).toLocaleString()}원</p>
                        )}
                        {transactionError && <p className="mt-1 text-red-600">{transactionError}</p>}
                        <div className="mt-3 flex gap-2">
                          <button
                            onClick={() => onRecordTransaction(reservation.id)}
                            disabled={recordingTransaction || !amountInput || Number(amountInput) <= 0}
                            className="rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
                          >
                            {recordingTransaction ? "기록 중..." : "매출 기록하기"}
                          </button>
                          <button
                            onClick={onSkipForNow}
                            disabled={recordingTransaction}
                            className="rounded-md border border-black px-4 py-2 disabled:opacity-50"
                          >
                            나중에
                          </button>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div className="mt-3 flex items-center justify-between border-t border-gray-100 pt-3">
                      <p className="text-gray-500">실제 매출: 아직 기록하지 않았어요</p>
                      <button
                        onClick={() => {
                          setOpenAmountFormId(reservation.id);
                          setAmountInput("");
                          setTransactionError(null);
                        }}
                        className="rounded-md border border-black px-3 py-1.5"
                      >
                        매출 기록하기
                      </button>
                    </div>
                  );
                })()}
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
