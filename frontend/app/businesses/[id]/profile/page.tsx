"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, CATEGORY_LABELS, type NaverLookupCandidate, type PartnerSuggestion } from "@/lib/api";

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
  const [description, setDescription] = useState("");
  const [brandTone, setBrandTone] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [openingHours, setOpeningHours] = useState("");
  const [holiday, setHoliday] = useState("");
  const [parking, setParking] = useState("");
  const [petPolicy, setPetPolicy] = useState("");
  const [reservationPolicy, setReservationPolicy] = useState("");
  const [takeoutPolicy, setTakeoutPolicy] = useState("");
  const [paymentMethods, setPaymentMethods] = useState("");
  const [faq, setFaq] = useState("");
  const [monthlyVisitorEstimate, setMonthlyVisitorEstimate] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [naverPlaceUrl, setNaverPlaceUrl] = useState<string | null>(null);
  const [naverMapUrl, setNaverMapUrl] = useState<string | null>(null);
  const [naverCandidate, setNaverCandidate] = useState<NaverLookupCandidate | null>(null);
  const [naverLoading, setNaverLoading] = useState(false);
  const [naverConnecting, setNaverConnecting] = useState(false);
  const [naverError, setNaverError] = useState<string | null>(null);

  const [expansionSuggestions, setExpansionSuggestions] = useState<PartnerSuggestion[] | null>(null);
  const [expansionLoading, setExpansionLoading] = useState(false);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    api
      .getOwnerProfile(token, id)
      .then((profile) => {
        setDescription(profile.description ?? "");
        setBrandTone(profile.brand_tone ?? "");
        setOpeningHours(textOf(profile.opening_hours));
        setHoliday(profile.holiday ?? "");
        setParking(profile.parking ?? "");
        setPetPolicy(profile.pet_policy ?? "");
        setReservationPolicy(profile.reservation_policy ?? "");
        setTakeoutPolicy(profile.takeout_policy ?? "");
        setPaymentMethods(textOf(profile.payment_methods));
        setFaq(textOf(profile.faq));
        setMonthlyVisitorEstimate(
          profile.monthly_visitor_estimate != null ? String(profile.monthly_visitor_estimate) : ""
        );
        setNaverPlaceUrl(profile.naver_place_url);
        setNaverMapUrl(profile.naver_map_url);
      })
      .finally(() => setLoaded(true));
  }, [id, token]);

  const onDraftWithAi = async () => {
    if (!token) return;
    setDraftError(null);
    setDrafting(true);
    try {
      const draft = await api.draftProfile(token, id);
      setDescription(draft.description);
      setBrandTone(draft.brand_tone);
    } catch (err) {
      setDraftError(err instanceof ApiError ? err.message : "초안 작성 중 오류가 발생했습니다.");
    } finally {
      setDrafting(false);
    }
  };

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
      await api.updateProfile(token, id, {
        naver_place_url: naverCandidate.naver_url,
        naver_map_url: naverCandidate.map_url,
      });
      setNaverPlaceUrl(naverCandidate.naver_url);
      setNaverMapUrl(naverCandidate.map_url);
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
        description: description || undefined,
        brand_tone: brandTone || undefined,
        opening_hours: openingHours ? { text: openingHours } : undefined,
        holiday: holiday || undefined,
        parking: parking || undefined,
        pet_policy: petPolicy || undefined,
        reservation_policy: reservationPolicy || undefined,
        takeout_policy: takeoutPolicy || undefined,
        payment_methods: paymentMethods ? { text: paymentMethods } : undefined,
        faq: faq ? { text: faq } : undefined,
        monthly_visitor_estimate: monthlyVisitorEstimate ? Number(monthlyVisitorEstimate) : undefined,
      });
      setSaved(true);
      if (expansionSuggestions === null) onAutoAnalyzeExpansion();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  const onAutoAnalyzeExpansion = async () => {
    if (!token) return;
    setExpansionLoading(true);
    try {
      const results = await api.analyzeExpansion(token, id);
      setExpansionSuggestions(results.slice(0, 4));
    } catch {
      // background convenience feature - a failure here shouldn't block onboarding
      setExpansionSuggestions([]);
    } finally {
      setExpansionLoading(false);
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
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold">가게 소개 & AI 말투</p>
          <button
            type="button"
            onClick={onDraftWithAi}
            disabled={drafting}
            className="rounded-md border border-black px-3 py-1 text-xs disabled:opacity-50"
          >
            {drafting ? "작성 중..." : "AI가 초안 써줄게요"}
          </button>
        </div>
        {draftError && <p className="text-sm text-red-600">{draftError}</p>}
        <label className="flex flex-col gap-1 text-sm">
          가게 소개
          <textarea
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 영종식당은 바지락 칼국수를 대표 메뉴로 하는 한식당입니다."
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          AI 말투
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 친근하고 정겨운 존댓말"
            value={brandTone}
            onChange={(e) => setBrandTone(e.target.value)}
          />
        </label>
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
            placeholder="예: 10인 이상 단체는 사전 전화 문의 필요"
            value={reservationPolicy}
            onChange={(e) => setReservationPolicy(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          포장 안내
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 포장 가능, 전화 주문 후 방문 수령"
            value={takeoutPolicy}
            onChange={(e) => setTakeoutPolicy(e.target.value)}
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
        <label className="flex flex-col gap-1 text-sm">
          자주 묻는 질문
          <textarea
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: Q. 단체석 있나요? A. 8인석 룸이 하나 있어요, 미리 전화 주세요."
            rows={3}
            value={faq}
            onChange={(e) => setFaq(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          예상 월 방문객 수 (선택)
          <input
            type="number"
            min="0"
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 2000"
            value={monthlyVisitorEstimate}
            onChange={(e) => setMonthlyVisitorEstimate(e.target.value)}
          />
          <span className="text-xs text-gray-500">
            입력해두면 다른 업체가 우리 가게와 제휴할 때 예상 효과(예상 매출 등)를 계산해드려요.
          </span>
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
            <a href={naverMapUrl ?? naverPlaceUrl} target="_blank" rel="noreferrer" className="underline">
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
                href={naverCandidate.map_url}
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

      {/* P0-3 (온보딩 완료 체감 순간) - 저장 직후엔 완료 축하 문구도, Home으로
          돌아갈 링크도 없어서 사장님이 "다 된 건가?" 하고 헤맬 수 있었다.
          기존 로직은 안 건드리고 이 완료 상태에 문구/링크만 추가한다. */}
      {saved && (
        <div className="mt-6 rounded-md border-2 border-black p-4">
          <p className="font-semibold">🎉 우리 가게 AI가 준비됐어요!</p>
          <p className="mt-1 text-sm text-gray-600">
            메뉴와 AI 정보 입력이 끝났어요. 아래에서 AI 답변을 직접 확인해보거나, Home에서 손님에게
            공개할 수 있어요.
          </p>
          <div className="mt-3 flex gap-2">
            <Link
              href={`/businesses/${id}`}
              className="rounded-md border border-black px-4 py-2 text-center text-sm"
            >
              AI 테스트해보기 →
            </Link>
            <Link
              href="/dashboard"
              className="rounded-md bg-black px-4 py-2 text-center text-sm text-white"
            >
              Home에서 공개하기 →
            </Link>
          </div>
        </div>
      )}

      {saved && expansionLoading && (
        <p className="mt-6 text-sm text-gray-500">사장님과 연계 가능성이 높은 업체를 찾는 중...</p>
      )}

      {saved && !expansionLoading && expansionSuggestions && expansionSuggestions.length > 0 && (
        <div className="mt-6 rounded-md border border-gray-200 p-4 text-sm">
          <p className="mb-3 font-semibold">사장님과 연계 가능성이 높은 업체를 찾았습니다</p>
          <ol className="flex flex-col gap-2">
            {expansionSuggestions.map((s, i) => (
              <li key={s.business_b_id} className="flex justify-between">
                <span>
                  {i + 1}. {s.name_ko} <span className="text-gray-500">({CATEGORY_LABELS[s.category]})</span>
                </span>
                <span className="text-gray-500">연관성 {s.score}점</span>
              </li>
            ))}
          </ol>
          <Link href={`/businesses/${id}/expansion`} className="mt-3 inline-block text-xs underline">
            자세히 보고 제휴 제안하기 →
          </Link>
        </div>
      )}

    </main>
  );
}
