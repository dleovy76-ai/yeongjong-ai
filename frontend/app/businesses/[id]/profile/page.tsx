"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";

function textOf(value: Record<string, unknown> | null): string {
  if (!value) return "";
  const text = value["text"];
  return typeof text === "string" ? text : "";
}

export default function BusinessProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();

  const [loaded, setLoaded] = useState(false);
  const [openingHours, setOpeningHours] = useState("");
  const [holiday, setHoliday] = useState("");
  const [parking, setParking] = useState("");
  const [petPolicy, setPetPolicy] = useState("");
  const [reservationPolicy, setReservationPolicy] = useState("");
  const [paymentMethods, setPaymentMethods] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    api
      .getProfile(id)
      .then((profile) => {
        setOpeningHours(textOf(profile.opening_hours));
        setHoliday(profile.holiday ?? "");
        setParking(profile.parking ?? "");
        setPetPolicy(profile.pet_policy ?? "");
        setReservationPolicy(profile.reservation_policy ?? "");
        setPaymentMethods(textOf(profile.payment_methods));
      })
      .finally(() => setLoaded(true));
  }, [id]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setSaved(false);
    setSubmitting(true);
    try {
      await api.updateProfile(token, id, {
        opening_hours: openingHours ? { text: openingHours } : undefined,
        holiday: holiday || undefined,
        parking: parking || undefined,
        pet_policy: petPolicy || undefined,
        reservation_policy: reservationPolicy || undefined,
        payment_methods: paymentMethods ? { text: paymentMethods } : undefined,
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!loaded) return null;

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <p className="mb-1 text-sm text-gray-500">Step 3 / 3 · AI 정보</p>
      <h1 className="mb-2 text-2xl font-bold">AI가 고객에게 답할 정보예요</h1>
      <p className="mb-8 text-sm text-gray-600">
        여기 적은 내용만 AI가 답변에 사용해요. 비워두면 AI는 &quot;확인이 필요합니다&quot;라고
        답합니다 — 확실하지 않은 건 추측해서 알려주지 않아요.
      </p>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          영업시간
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 매일 10:00 - 21:00"
            value={openingHours}
            onChange={(e) => setOpeningHours(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          휴무일
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 매주 월요일"
            value={holiday}
            onChange={(e) => setHoliday(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          주차
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 매장 앞 3대 무료 주차 가능"
            value={parking}
            onChange={(e) => setParking(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          반려동물 동반
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 실외석만 동반 가능"
            value={petPolicy}
            onChange={(e) => setPetPolicy(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          예약 안내
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 전화로만 예약 가능"
            value={reservationPolicy}
            onChange={(e) => setReservationPolicy(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          결제 수단
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 카드, 현금, 카카오페이"
            value={paymentMethods}
            onChange={(e) => setPaymentMethods(e.target.value)}
          />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {saved && <p className="text-sm text-green-700">저장했어요.</p>}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "저장 중..." : "저장하기"}
        </button>
      </form>
    </main>
  );
}
