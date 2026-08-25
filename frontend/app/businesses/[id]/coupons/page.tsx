"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, type Coupon, type CouponDiscountType, type UnrecordedCouponIssue } from "@/lib/api";

const STATUS_LABEL: Record<Coupon["status"], string> = {
  DRAFT: "준비 중 (비공개)",
  ACTIVE: "공개 중",
  EXPIRED: "만료됨",
  DISABLED: "비활성화됨",
};

function formatWon(amount: string): string {
  return `${Number(amount).toLocaleString()}원`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
}

interface PendingIssue {
  issue: UnrecordedCouponIssue;
  amountInput: string;
  formOpen: boolean;
  isFresh: boolean; // 방금 이 화면에서 사용 처리한 것(과거에서 불러온 게 아님)
  recording: boolean;
  error: string | null;
  transaction: { amount: string } | null;
}

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
  const [redeeming, setRedeeming] = useState(false);
  const [redeemError, setRedeemError] = useState<string | null>(null);
  // P1-3.1 - 처음엔 "이번 방문 중 처리한 것만" 세션에만 있었는데, 새로고침하면
  // 사라지는 문제가 있었다. 이제 listUnrecordedCouponIssues로 서버에서
  // "사용됐지만 매출 미기록"인 건을 그대로 불러와 여기 시드로 채운다 -
  // 나중에 다시 들어와도 그대로 남아있다.
  const [pendingIssues, setPendingIssues] = useState<PendingIssue[]>([]);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    if (!token) return;
    Promise.all([api.listCoupons(id, token), api.listUnrecordedCouponIssues(token, id).catch(() => [])])
      .then(([couponList, unrecorded]) => {
        setCoupons(couponList);
        setPendingIssues(
          unrecorded.map((issue) => ({
            issue,
            amountInput: "",
            formOpen: false,
            isFresh: false,
            recording: false,
            error: null,
            transaction: null,
          }))
        );
      })
      .catch(() => setCoupons([]));
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

  const updatePending = (issueId: string, patch: Partial<PendingIssue>) => {
    setPendingIssues((prev) => prev.map((p) => (p.issue.id === issueId ? { ...p, ...patch } : p)));
  };

  const onRedeem = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setRedeemError(null);
    setRedeeming(true);
    try {
      const claim = await api.redeemCoupon(token, id, redeemCode.trim());
      const couponTitle = coupons?.find((c) => c.id === claim.coupon_id)?.title ?? "";
      setPendingIssues((prev) => [
        {
          issue: { ...claim, coupon_title: couponTitle },
          amountInput: "",
          formOpen: true,
          isFresh: true,
          recording: false,
          error: null,
          transaction: null,
        },
        ...prev,
      ]);
      setRedeemCode("");
    } catch (err) {
      setRedeemError(err instanceof ApiError ? err.message : "쿠폰 사용 처리 중 오류가 발생했습니다.");
    } finally {
      setRedeeming(false);
    }
  };

  const onRecordAmount = async (issueId: string) => {
    if (!token) return;
    const entry = pendingIssues.find((p) => p.issue.id === issueId);
    if (!entry) return;
    const amount = Number(entry.amountInput);
    if (!entry.amountInput || amount <= 0) return;
    updatePending(issueId, { recording: true, error: null });
    try {
      const transaction = await api.createTransaction(token, id, {
        amount: entry.amountInput,
        coupon_issue_id: issueId,
      });
      updatePending(issueId, { transaction, formOpen: false, recording: false });
    } catch (err) {
      updatePending(issueId, {
        error: err instanceof ApiError ? err.message : "매출 기록 중 오류가 발생했습니다.",
        recording: false,
      });
    }
  };

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">쿠폰 관리</h1>
      <p className="mb-8 text-sm text-gray-600">
        쿠폰을 받은 손님이 실제로 사용했는지 확인하고, 사용한 손님의 매출까지 기록할 수 있어요.
      </p>

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
              <div className="mt-3 grid grid-cols-2 gap-2 border-t border-gray-100 pt-3">
                <div>
                  <p className="text-gray-500">🎟 손님에게 발급</p>
                  <p className="font-semibold">{coupon.issued_count}건</p>
                </div>
                <div>
                  <p className="text-gray-500">✅ 실제 사용</p>
                  <p className="font-semibold">{coupon.redeemed_count}건</p>
                  {coupon.redeemed_count === 0 && (
                    <p className="mt-1 text-gray-500">아직 사용된 쿠폰이 없어요.</p>
                  )}
                </div>
              </div>
            </li>
          ))}
          {coupons.length === 0 && (
            <p className="text-gray-500">아직 만든 쿠폰이 없어요. 아래에서 첫 쿠폰을 만들어보세요.</p>
          )}
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

      <div className="mb-8 flex flex-col gap-4 rounded-md border border-gray-200 p-4">
        <h2 className="font-semibold">손님 쿠폰 코드 사용 처리</h2>
        <form onSubmit={onRedeem} className="flex flex-col gap-3">
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
          {redeemError && <p className="text-sm text-red-600">{redeemError}</p>}
          <button
            type="submit"
            disabled={redeeming}
            className="rounded-md border border-black px-4 py-2 disabled:opacity-50"
          >
            {redeeming ? "처리 중..." : "사용 처리"}
          </button>
        </form>
      </div>

      {pendingIssues.length > 0 && (
        <div className="flex flex-col gap-3">
          <h2 className="font-semibold">🎟 아직 매출을 기록하지 않은 쿠폰</h2>
          {pendingIssues.map((entry) => (
            <div key={entry.issue.id} className="rounded-md border border-gray-200 bg-gray-50 p-3 text-sm">
              <p className="font-semibold">{entry.issue.coupon_title || "쿠폰"}</p>
              <p className="mt-1 text-gray-500">
                사용 확인: {entry.issue.redeemed_at ? formatDate(entry.issue.redeemed_at) : "-"} · 코드{" "}
                {entry.issue.code}
              </p>

              {entry.transaction ? (
                <>
                  <p className="mt-2 text-gray-700">
                    실제 매출 <span className="font-semibold">{formatWon(entry.transaction.amount)}</span>
                  </p>
                  <p className="mt-1 text-green-700">매출이 기록됐어요. 쿠폰을 사용한 손님의 매출로 연결됐어요.</p>
                </>
              ) : entry.formOpen ? (
                <>
                  {entry.isFresh && <p className="mt-2 font-semibold">🎉 쿠폰 사용이 확인됐어요</p>}
                  <p className="mt-1 text-gray-600">
                    실제 결제금액을 기록하면 AI를 통해 연결된 매출로 확인할 수 있어요.
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <span className="text-lg font-semibold">₩</span>
                    <input
                      type="number"
                      min="1"
                      inputMode="numeric"
                      placeholder="15000"
                      className="w-32 rounded-md border border-gray-300 px-3 py-2 text-base normal-case"
                      value={entry.amountInput}
                      onChange={(e) => updatePending(entry.issue.id, { amountInput: e.target.value })}
                    />
                  </div>
                  {entry.amountInput && Number(entry.amountInput) > 0 && (
                    <p className="mt-1 text-gray-500">{Number(entry.amountInput).toLocaleString()}원</p>
                  )}
                  {entry.error && <p className="mt-1 text-red-600">{entry.error}</p>}
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => onRecordAmount(entry.issue.id)}
                      disabled={entry.recording || !entry.amountInput || Number(entry.amountInput) <= 0}
                      className="rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
                    >
                      {entry.recording ? "기록 중..." : "매출 기록하기"}
                    </button>
                    <button
                      onClick={() => updatePending(entry.issue.id, { formOpen: false })}
                      disabled={entry.recording}
                      className="rounded-md border border-black px-4 py-2 disabled:opacity-50"
                    >
                      나중에
                    </button>
                  </div>
                </>
              ) : (
                <div className="mt-2 flex items-center justify-between">
                  <p className="text-gray-500">실제 매출: 아직 기록하지 않았어요</p>
                  <button
                    onClick={() => updatePending(entry.issue.id, { formOpen: true })}
                    className="rounded-md border border-black px-3 py-1.5"
                  >
                    매출 기록하기
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
