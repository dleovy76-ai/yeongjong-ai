"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import { ChatWidget } from "@/components/ChatWidget";
import { api, ApiError, CATEGORY_LABELS, type Business, type BusinessProfile, type Coupon, type Menu } from "@/lib/api";

function textOf(value: Record<string, unknown> | null): string | null {
  if (!value) return null;
  const text = value["text"];
  return typeof text === "string" && text ? text : null;
}

export default function BusinessDetailPage() {
  const { id } = useParams<{ id: string }>();
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

  useEffect(() => {
    Promise.all([api.getBusiness(id), api.listMenus(id)])
      .then(([b, m]) => {
        setBusiness(b);
        setMenus(m);
      })
      .catch(() => setNotFound(true));
    api.getProfile(id).then(setProfile).catch(() => setProfile(null));
    api.listCoupons(id).then(setCoupons).catch(() => setCoupons([]));
  }, [id]);

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
          <ul className="flex flex-col gap-1 text-sm">
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

      <div className="mb-8">
        <h2 className="mb-2 font-semibold">예약 요청</h2>
        {resvDone ? (
          <p className="rounded-md border border-gray-200 p-3 text-sm text-green-700">
            예약 요청이 접수되었어요. 업체에서 확인 후 확정 연락을 드려요.
          </p>
        ) : (
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
        )}
      </div>

      <h2 className="mb-2 font-semibold">AI에게 물어보세요</h2>
      <ChatWidget
        greeting="안녕하세요! 영업시간, 메뉴, 주차, 반려동물 동반 여부 등 궁금한 걸 물어보세요."
        placeholder="예: 주차 가능한가요?"
        onSend={async (message) => (await api.chat(business.id, message)).reply}
      />
    </main>
  );
}
