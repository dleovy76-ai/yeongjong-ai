"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import { ChatWidget } from "@/components/ChatWidget";
import { useAuth } from "@/lib/auth-context";
import {
  api,
  ApiError,
  CATEGORY_LABELS,
  type Business,
  type BusinessProfile,
  type ChatHistoryItem,
  type Coupon,
  type Menu,
  type ReservationDraft,
} from "@/lib/api";

function textOf(value: Record<string, unknown> | null): string | null {
  if (!value) return null;
  const text = value["text"];
  return typeof text === "string" && text ? text : null;
}

// P1-6 - 이름/연락처/날짜/시간/인원 전부 채워졌을 때만 [예약 확정]을 누를 수
// 있다. Reservation 스키마 자체가 이 4개(연락처 포함)를 필수로 요구하므로
// (backend/schemas/reservations.py), 여기서 막지 않으면 어차피 API가 막는다 -
// 다만 손님에게는 버튼을 눌러보기 전에 미리 알려주는 게 낫다.
function isDraftComplete(
  draft: ReservationDraft
): draft is ReservationDraft & { customer_name: string; customer_phone: string; date: string; time: string; party_size: number } {
  return Boolean(draft.customer_name && draft.customer_phone && draft.date && draft.time && draft.party_size);
}

function formatDraftField(value: string | number | null, unit?: string): string {
  if (value === null || value === "") return "확인 필요";
  return unit ? `${value}${unit}` : String(value);
}

export default function BusinessDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const [business, setBusiness] = useState<Business | null>(null);
  const [profile, setProfile] = useState<BusinessProfile | null>(null);
  const [menus, setMenus] = useState<Menu[]>([]);
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [claimedCodes, setClaimedCodes] = useState<Record<string, string>>({});
  const [claimErrors, setClaimErrors] = useState<Record<string, string>>({});
  const [notFound, setNotFound] = useState(false);

  const [resvName, setResvName] = useState("");
  const [resvPhone, setResvPhone] = useState("");
  const [resvTime, setResvTime] = useState("");
  const [resvPartySize, setResvPartySize] = useState("2");
  const [resvNotes, setResvNotes] = useState("");
  const [resvSubmitting, setResvSubmitting] = useState(false);
  const [resvError, setResvError] = useState<string | null>(null);
  const [resvDone, setResvDone] = useState(false);
  // P0-2 (예약 경로 중복 정리) - 수동 폼과 AI 대화형 예약이 동시에 펼쳐져
  // 있으면 처음 온 손님이 뭘 써야 할지 헷갈린다. AI 대화를 기본 경로로
  // 두고, 수동 폼은 원하는 사람만 펼쳐보는 대안으로 접어둔다 - 폼 자체의
  // 로직/필드는 전혀 안 건드림.
  const [showManualForm, setShowManualForm] = useState(false);

  const [reservationDraft, setReservationDraft] = useState<ReservationDraft | null>(null);
  const [draftConfirmed, setDraftConfirmed] = useState(false);
  const [draftConfirming, setDraftConfirming] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);

  useEffect(() => {
    // authLoading이 끝날 때까지 기다렸다가 부른다 - 로그인한 사장님이 자기
    // DRAFT/DISABLED 업체를 "AI 미리보기"로 볼 때 토큰 없이 먼저 요청하면
    // 404가 나므로(AUDIT P1), 토큰이 준비된 뒤 한 번만 요청한다.
    if (authLoading) return;
    Promise.all([api.getBusiness(id, token), api.listMenus(id)])
      .then(([b, m]) => {
        setBusiness(b);
        setMenus(m);
      })
      .catch(() => setNotFound(true));
    api.getProfile(id, token).then(setProfile).catch(() => setProfile(null));
    api.listCoupons(id).then(setCoupons).catch(() => setCoupons([]));
  }, [id, token, authLoading]);

  const claimCoupon = async (couponId: string) => {
    try {
      const claim = await api.issueCoupon(id, couponId);
      setClaimedCodes((prev) => ({ ...prev, [couponId]: claim.code }));
    } catch (err) {
      setClaimErrors((prev) => ({
        ...prev,
        [couponId]: err instanceof ApiError ? err.message : "쿠폰을 받지 못했습니다.",
      }));
    }
  };

  const onReserve = async (e: FormEvent) => {
    e.preventDefault();
    if (!resvTime) return;
    setResvError(null);
    setResvSubmitting(true);
    try {
      await api.createReservation(id, {
        customer_name: resvName,
        customer_phone: resvPhone,
        reservation_time: new Date(resvTime).toISOString(),
        party_size: Number(resvPartySize),
        notes: resvNotes || undefined,
      });
      setResvDone(true);
      setResvName("");
      setResvPhone("");
      setResvTime("");
      setResvPartySize("2");
      setResvNotes("");
    } catch (err) {
      setResvError(err instanceof ApiError ? err.message : "예약 요청 중 오류가 발생했습니다.");
    } finally {
      setResvSubmitting(false);
    }
  };

  const onConfirmReservationDraft = async () => {
    if (!reservationDraft || !isDraftComplete(reservationDraft)) return;
    setDraftConfirming(true);
    setDraftError(null);
    try {
      // P1-6 - AI는 예약을 만들지 않는다. 이 클릭이 유일하게 예약을 만드는
      // 지점이고, 수동 폼과 완전히 동일한 기존 createReservation()을 그대로
      // 쓴다(새 예약 생성 경로를 만들지 않음).
      await api.createReservation(id, {
        customer_name: reservationDraft.customer_name,
        customer_phone: reservationDraft.customer_phone,
        reservation_time: new Date(`${reservationDraft.date}T${reservationDraft.time}`).toISOString(),
        party_size: reservationDraft.party_size,
        notes: reservationDraft.notes || undefined,
      });
      setDraftConfirmed(true);
      setReservationDraft(null);
    } catch (err) {
      setDraftError(err instanceof ApiError ? err.message : "예약 확정 중 오류가 발생했습니다.");
    } finally {
      setDraftConfirming(false);
    }
  };

  if (notFound) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-12">
        <p className="text-gray-500">업체를 찾을 수 없어요.</p>
      </main>
    );
  }

  if (!business) return null;

  const openingHours = textOf(profile?.opening_hours ?? null);

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <p className="text-sm text-gray-500">{CATEGORY_LABELS[business.category]}</p>
      <h1 className="mb-2 text-2xl font-bold">{business.name_ko}</h1>
      <p className="mb-1 text-sm text-gray-600">{business.address}</p>
      {business.phone && <p className="mb-1 text-sm text-gray-600">{business.phone}</p>}
      <div className="mb-6">
        {profile?.naver_place_url && (
          <a href={profile.naver_place_url} target="_blank" rel="noreferrer" className="text-sm underline">
            네이버에서 리뷰·영업시간 더 보기
          </a>
        )}
      </div>

      <dl className="mb-8 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        {openingHours && (
          <>
            <dt className="text-gray-500">영업시간</dt>
            <dd>{openingHours}</dd>
          </>
        )}
        {profile?.holiday && (
          <>
            <dt className="text-gray-500">휴무일</dt>
            <dd>{profile.holiday}</dd>
          </>
        )}
        {profile?.parking && (
          <>
            <dt className="text-gray-500">주차</dt>
            <dd>{profile.parking}</dd>
          </>
        )}
        {profile?.pet_policy && (
          <>
            <dt className="text-gray-500">반려동물</dt>
            <dd>{profile.pet_policy}</dd>
          </>
        )}
      </dl>

      {coupons.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-2 font-semibold">쿠폰</h2>
          <ul className="flex flex-col gap-3">
            {coupons.map((coupon) => (
              <li key={coupon.id} className="rounded-md border border-gray-200 p-3 text-sm">
                <p className="font-semibold">{coupon.title}</p>
                {coupon.description && <p className="text-gray-500">{coupon.description}</p>}
                {claimedCodes[coupon.id] ? (
                  <p className="mt-2 rounded bg-gray-100 px-3 py-2 font-mono text-base">
                    코드: {claimedCodes[coupon.id]} (매장에서 보여주세요)
                  </p>
                ) : (
                  <button
                    onClick={() => claimCoupon(coupon.id)}
                    className="mt-2 rounded-md border border-black px-3 py-1.5"
                  >
                    쿠폰 받기
                  </button>
                )}
                {claimErrors[coupon.id] && (
                  <p className="mt-1 text-red-600">{claimErrors[coupon.id]}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {menus.length > 0 && (
        <div className="mb-8">
          <h2 className="mb-2 font-semibold">메뉴</h2>
          <ul className="mb-4 flex flex-col gap-1 text-sm">
            {menus.map((m) => (
              <li key={m.id} className="flex justify-between">
                <span>
                  {m.is_signature && "⭐ "}
                  {m.name}
                </span>
                <span>{Number(m.price).toLocaleString()}원</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <h2 className="mb-2 font-semibold">AI에게 물어보세요</h2>
      <ChatWidget
        greeting="안녕하세요! 영업시간, 주차, 반려동물 동반 여부부터 메뉴 추천, 예약까지 편하게 물어보세요."
        placeholder="예: 내일 저녁 7시에 3명 예약하고 싶어요"
        onSend={async (message, history) => {
          const res = await api.chat(business.id, message, history as ChatHistoryItem[]);
          // P1-6 - 매 응답마다 대화 전체를 다시 분석한 결과로 완전히 덮어쓴다
          // (patch가 아니라 재도출) - 정정 발화가 별도 로직 없이 자연스럽게
          // 반영되고, AI가 더 이상 예약 의도가 없다고 판단하면 카드도 사라진다.
          setReservationDraft(res.reservation_draft);
          if (res.reservation_draft) setDraftConfirmed(false);
          return { text: res.reply, images: res.menu_images };
        }}
      />

      {reservationDraft && (
        <div className="mt-4 rounded-md border-2 border-black p-4 text-sm">
          <p className="font-semibold">예약 내용을 확인해주세요</p>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            <dt className="text-gray-500">이름</dt>
            <dd>{formatDraftField(reservationDraft.customer_name)}</dd>
            <dt className="text-gray-500">연락처</dt>
            <dd>{formatDraftField(reservationDraft.customer_phone)}</dd>
            <dt className="text-gray-500">날짜</dt>
            <dd>{formatDraftField(reservationDraft.date)}</dd>
            <dt className="text-gray-500">시간</dt>
            <dd>{formatDraftField(reservationDraft.time)}</dd>
            <dt className="text-gray-500">인원</dt>
            <dd>{formatDraftField(reservationDraft.party_size, "명")}</dd>
          </dl>
          {draftError && <p className="mt-2 text-red-600">{draftError}</p>}
          <button
            onClick={onConfirmReservationDraft}
            disabled={!isDraftComplete(reservationDraft) || draftConfirming}
            className="mt-3 rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
          >
            {draftConfirming ? "확정 중..." : "예약 확정"}
          </button>
          <p className="mt-2 text-xs text-gray-500">
            확정을 누르면 예약 요청이 접수되고, 사장님이 확인 후 확정해드립니다.
          </p>
        </div>
      )}
      {draftConfirmed && (
        <p className="mt-4 rounded-md border border-gray-200 p-3 text-sm text-green-700">
          예약 요청이 접수되었어요. 업체에서 확인 후 확정 연락을 드려요.
        </p>
      )}

      <div className="mt-8">
        {resvDone ? (
          <p className="rounded-md border border-gray-200 p-3 text-sm text-green-700">
            예약 요청이 접수되었어요. 업체에서 확인 후 확정 연락을 드려요.
          </p>
        ) : showManualForm ? (
          <>
            <h2 className="mb-2 font-semibold">양식으로 예약하기</h2>
            <form onSubmit={onReserve} className="flex flex-col gap-3 text-sm">
              <label className="flex flex-col gap-1">
                이름 *
                <input
                  className="rounded-md border border-gray-300 px-3 py-2"
                  value={resvName}
                  onChange={(e) => setResvName(e.target.value)}
                  required
                />
              </label>
              <label className="flex flex-col gap-1">
                연락처 *
                <input
                  className="rounded-md border border-gray-300 px-3 py-2"
                  placeholder="010-1234-5678"
                  value={resvPhone}
                  onChange={(e) => setResvPhone(e.target.value)}
                  required
                />
              </label>
              <div className="flex gap-2">
                <label className="flex flex-1 flex-col gap-1">
                  날짜 및 시간 *
                  <input
                    type="datetime-local"
                    className="rounded-md border border-gray-300 px-3 py-2"
                    value={resvTime}
                    onChange={(e) => setResvTime(e.target.value)}
                    required
                  />
                </label>
                <label className="flex flex-col gap-1">
                  인원 *
                  <input
                    type="number"
                    min="1"
                    className="w-20 rounded-md border border-gray-300 px-3 py-2"
                    value={resvPartySize}
                    onChange={(e) => setResvPartySize(e.target.value)}
                    required
                  />
                </label>
              </div>
              <label className="flex flex-col gap-1">
                요청사항 (선택)
                <input
                  className="rounded-md border border-gray-300 px-3 py-2"
                  placeholder="예: 창가 자리 부탁드려요"
                  value={resvNotes}
                  onChange={(e) => setResvNotes(e.target.value)}
                />
              </label>
              {resvError && <p className="text-red-600">{resvError}</p>}
              <button
                type="submit"
                disabled={resvSubmitting}
                className="rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
              >
                {resvSubmitting ? "요청 중..." : "예약 요청하기"}
              </button>
            </form>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setShowManualForm(true)}
            className="text-sm text-gray-600 underline"
          >
            AI 대화 대신 양식으로 직접 예약할게요
          </button>
        )}
      </div>
    </main>
  );
}
