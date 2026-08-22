"use client";

import { useEffect, useState } from "react";
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
      {business.phone && <p className="mb-6 text-sm text-gray-600">{business.phone}</p>}

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

      <h2 className="mb-2 font-semibold">AI에게 물어보세요</h2>
      <ChatWidget
        greeting="안녕하세요! 영업시간, 메뉴, 주차, 반려동물 동반 여부 등 궁금한 걸 물어보세요."
        placeholder="예: 주차 가능한가요?"
        onSend={async (message) => (await api.chat(business.id, message)).reply}
      />
    </main>
  );
}
