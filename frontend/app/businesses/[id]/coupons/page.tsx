"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type Coupon, type CouponDiscountType } from "@/lib/api";

const STATUS_LABEL: Record<Coupon["status"], string> = {
  DRAFT: "준비 중 (비공개)",
  ACTIVE: "공개 중",
  EXPIRED: "만료됨",
  DISABLED: "비활성화됨",
};

export default function CouponsPage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();

  const [coupons, setCoupons] = useState<Coupon[] | null>(null);
  const [title, setTitle] = useState("");
  const [discountType, setDiscountType] = useState<CouponDiscountType>("PERCENTAGE");
  const [discountValue, setDiscountValue] = useState("");
  const [conditions, setConditions] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [redeemCode, setRedeemCode] = useState("");
  const [redeemAmount, setRedeemAmount] = useState("");
  const [redeemResult, setRedeemResult] = useState<string | null>(null);
  const [redeemError, setRedeemError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    api.listCoupons(id, token).then(setCoupons).catch(() => setCoupons([]));
  }, [id, token]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setSubmitting(true);
    try {
      const coupon = await api.createCoupon(token, id, {
        title,
        discount_type: discountType,
        discount_value: discountValue,
        conditions: conditions || undefined,
      });
      setCoupons((prev) => [...(prev ?? []), coupon]);
      setTitle("");
      setDiscountValue("");
      setConditions("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "쿠폰 생성 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleStatus = async (coupon: Coupon) => {
    if (!token) return;
    const nextStatus = coupon.status === "ACTIVE" ? "DRAFT" : "ACTIVE";
    const updated = await api.updateCoupon(token, id, coupon.id, { status: nextStatus });
    setCoupons((prev) => prev?.map((c) => (c.id === updated.id ? updated : c)) ?? null);
  };

  const onRedeem = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setRedeemError(null);
    setRedeemResult(null);
    try {
      const claim = await api.redeemCoupon(token, id, redeemCode.trim());
      let resultText = `사용 처리 완료! (코드: ${claim.code})`;
      if (redeemAmount.trim()) {
        await api.createTransaction(token, id, { amount: redeemAmount.trim(), coupon_issue_id: claim.id });
        resultText += ` · 거래액 ${Number(redeemAmount).toLocaleString()}원 기록됨`;
      }
      setRedeemResult(resultText);
      setRedeemCode("");
      setRedeemAmount("");
    } catch (err) {
      setRedeemError(err instanceof ApiError ? err.message : "쿠폰 사용 처리 중 오류가 발생했습니다.");
    }
  };

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <h1 className="mb-8 text-2xl font-bold">쿠폰 관리</h1>

      {coupons === null ? (
        <p className="text-gray-500">불러오는 중...</p>
      ) : (
        <ul className="mb-8 flex flex-col gap-2">
          {coupons.map((coupon) => (
            <li key={coupon.id} className="rounded-md border border-gray-200 p-3 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold">{coupon.title}</p>
                  <p className="text-gray-500">
                    {coupon.discount_type === "PERCENTAGE"
                      ? `${coupon.discount_value}% 할인`
                      : `${Number(coupon.discount_value).toLocaleString()}원 할인`}{" "}
                    · {STATUS_LABEL[coupon.status]}
                  </p>
                </div>
                {(coupon.status === "ACTIVE" || coupon.status === "DRAFT") && (
                  <button
                    onClick={() => toggleStatus(coupon)}
                    className="rounded-md border border-black px-3 py-1.5"
                  >
                    {coupon.status === "ACTIVE" ? "비공개로 전환" : "공개하기"}
                  </button>
                )}
              </div>
            </li>
          ))}
          {coupons.length === 0 && <p className="text-gray-500">아직 등록된 쿠폰이 없어요.</p>}
        </ul>
      )}

      <form onSubmit={onCreate} className="mb-10 flex flex-col gap-4">
        <h2 className="font-semibold">새 쿠폰 만들기</h2>
        <label className="flex flex-col gap-1 text-sm">
          쿠폰명 *
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 아메리카노 20% 할인"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
        </label>
        <div className="flex gap-2">
          <label className="flex flex-1 flex-col gap-1 text-sm">
            할인 방식
            <select
              className="rounded-md border border-gray-300 px-3 py-2"
              value={discountType}
              onChange={(e) => setDiscountType(e.target.value as CouponDiscountType)}
            >
              <option value="PERCENTAGE">퍼센트(%)</option>
              <option value="FIXED_AMOUNT">정액(원)</option>
            </select>
          </label>
          <label className="flex flex-1 flex-col gap-1 text-sm">
            할인 값 *
            <input
              type="number"
              min="0"
              className="rounded-md border border-gray-300 px-3 py-2"
              value={discountValue}
              onChange={(e) => setDiscountValue(e.target.value)}
              required
            />
          </label>
        </div>
        <label className="flex flex-col gap-1 text-sm">
          조건 (선택)
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 1인 1회, 다른 할인과 중복 불가"
            value={conditions}
            onChange={(e) => setConditions(e.target.value)}
          />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "생성 중..." : "쿠폰 만들기"}
        </button>
      </form>

      <form onSubmit={onRedeem} className="flex flex-col gap-4 rounded-md border border-gray-200 p-4">
        <h2 className="font-semibold">손님 쿠폰 코드 사용 처리</h2>
        <p className="text-sm text-gray-600">
          손님이 보여준 코드를 입력하면 사용 완료로 처리돼요. 한 번 처리한 코드는 다시 쓸 수 없어요.
        </p>
        <input
          className="rounded-md border border-gray-300 px-3 py-2 uppercase"
          placeholder="예: HMCARD7Q"
          value={redeemCode}
          onChange={(e) => setRedeemCode(e.target.value)}
          required
        />
        <label className="flex flex-col gap-1 text-sm">
          실제 결제 금액 (선택 - 입력하면 이번 달 성과에 AI 연관 매출로 잡혀요)
          <input
            type="number"
            min="0"
            className="rounded-md border border-gray-300 px-3 py-2 normal-case"
            placeholder="예: 15000"
            value={redeemAmount}
            onChange={(e) => setRedeemAmount(e.target.value)}
          />
        </label>
        {redeemError && <p className="text-sm text-red-600">{redeemError}</p>}
        {redeemResult && <p className="text-sm text-green-700">{redeemResult}</p>}
        <button type="submit" className="rounded-md border border-black px-4 py-2">
          사용 처리
        </button>
      </form>
    </main>
  );
}
