"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type NaverLookupCandidate } from "@/lib/api";

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

  const [naverPlaceUrl, setNaverPlaceUrl] = useState<string | null>(null);
  const [naverCandidate, setNaverCandidate] = useState<NaverLookupCandidate | null>(null);
  const [naverLoading, setNaverLoading] = useState(false);
  const [naverConnecting, setNaverConnecting] = useState(false);
  const [naverError, setNaverError] = useState<string | null>(null);

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
        setNaverPlaceUrl(profile.naver_place_url);
      })
      .finally(() => setLoaded(true));
  }, [id]);

  const onFindOnNaver = async () => {
    if (!token) return;
    setNaverError(null);
    setNaverCandidate(null);
    setNaverLoading(true);
    try {
      const candidate = await api.naverLookup(token, id);
      setNaverCandidate(candidate);
    } catch (err) {
      setNaverError(err instanceof ApiError ? err.message : "네이버 검색 중 오류가 발생했습니다.");
    } finally {
      setNaverLoading(false);
    }
  };

  const onConfirmNaverLink = async () => {
    if (!token || !naverCandidate) return;
    setNaverConnecting(true);
    try {
      await api.updateProfile(token, id, { naver_place_url: naverCandidate.naver_url });
      setNaverPlaceUrl(naverCandidate.naver_url);
      setNaverCandidate(null);
    } catch (err) {
      setNaverError(err instanceof ApiError ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setNaverConnecting(false);
    }
  };

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

      <div className="mt-10 rounded-md border border-gray-200 p-4 text-sm">
        <h2 className="mb-2 font-semibold">네이버 플레이스 연결</h2>
        <p className="mb-3 text-gray-600">
          손님이 리뷰, 사진, 정확한 영업시간을 볼 수 있게 네이버 플레이스 페이지를 연결해요.
        </p>

        {naverPlaceUrl && !naverCandidate && (
          <p className="mb-3">
            연결됨:{" "}
            <a href={naverPlaceUrl} target="_blank" rel="noreferrer" className="underline">
              네이버에서 열기
            </a>
          </p>
        )}

        {naverCandidate ? (
          <div className="rounded-md border border-gray-200 p-3">
            <p className="font-semibold">{naverCandidate.title}</p>
            <p className="text-gray-500">{naverCandidate.road_address}</p>
            <p className="mt-1">
              {naverCandidate.verified ? (
                <span className="text-green-700">네이버에서 확인된 업체예요</span>
              ) : (
                <span className="text-gray-500">네이버에서 확인되지 않았어요 — 직접 확인해주세요</span>
              )}
            </p>
            <div className="mt-3 flex gap-2">
              <a
                href={naverCandidate.naver_url}
                target="_blank"
                rel="noreferrer"
                className="rounded-md border border-black px-3 py-1.5"
              >
                열어서 확인
              </a>
              <button
                onClick={onConfirmNaverLink}
                disabled={naverConnecting}
                className="rounded-md bg-black px-3 py-1.5 text-white disabled:opacity-50"
              >
                {naverConnecting ? "연결 중..." : "네, 맞아요 연결하기"}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={onFindOnNaver}
            disabled={naverLoading}
            className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
          >
            {naverLoading ? "찾는 중..." : naverPlaceUrl ? "다시 찾기" : "AI가 네이버에서 찾아보기"}
          </button>
        )}
        {naverError && <p className="mt-2 text-red-600">{naverError}</p>}
      </div>

      {saved && (
        <Link
          href={`/businesses/${id}`}
          className="mt-6 inline-block rounded-md border border-black px-4 py-2 text-center"
        >
          AI 테스트해보기 →
        </Link>
      )}
    </main>
  );
}
