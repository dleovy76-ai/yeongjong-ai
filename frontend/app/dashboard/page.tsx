"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, type Business, ApiError } from "@/lib/api";

const STATUS_LABEL: Record<Business["status"], string> = {
  DRAFT: "준비 중 (비공개)",
  ACTIVE: "공개 중",
  DISABLED: "비활성화됨",
};

export default function DashboardPage() {
  const { token, user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [businesses, setBusinesses] = useState<Business[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      router.push("/login");
      return;
    }
    api
      .myBusinesses(token)
      .then(setBusinesses)
      .catch((err) => setError(err instanceof ApiError ? err.message : "불러오기 실패"));
  }, [authLoading, token, router]);

  const toggleStatus = async (business: Business) => {
    if (!token) return;
    setTogglingId(business.id);
    try {
      const nextStatus = business.status === "ACTIVE" ? "DRAFT" : "ACTIVE";
      const updated = await api.updateBusiness(token, business.id, { status: nextStatus });
      setBusinesses((prev) => prev?.map((b) => (b.id === updated.id ? updated : b)) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "상태 변경 실패");
    } finally {
      setTogglingId(null);
    }
  };

  if (authLoading || !user) return null;

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-bold">내 업체</h1>
        <Link href="/businesses/new" className="rounded-md bg-black px-4 py-2 text-sm text-white">
          + 새 업체 등록
        </Link>
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {businesses === null ? (
        <p className="text-gray-500">불러오는 중...</p>
      ) : businesses.length === 0 ? (
        <p className="text-gray-500">
          아직 등록한 업체가 없어요. 위 버튼으로 첫 업체를 등록해 보세요.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {businesses.map((business) => (
            <li key={business.id} className="rounded-md border border-gray-200 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold">{business.name_ko}</p>
                  <p className="text-sm text-gray-500">{STATUS_LABEL[business.status]}</p>
                </div>
                <button
                  onClick={() => toggleStatus(business)}
                  disabled={togglingId === business.id}
                  className="rounded-md border border-black px-3 py-1.5 text-sm disabled:opacity-50"
                >
                  {business.status === "ACTIVE" ? "비공개로 전환" : "공개하기"}
                </button>
              </div>
              <div className="mt-3 flex gap-4 text-sm">
                <Link href={`/businesses/${business.id}/menus`} className="underline">
                  메뉴 관리
                </Link>
                <Link href={`/businesses/${business.id}/profile`} className="underline">
                  AI 정보 입력
                </Link>
                <Link href={`/businesses/${business.id}/coupons`} className="underline">
                  쿠폰 관리
                </Link>
                <Link href={`/businesses/${business.id}/performance`} className="underline">
                  성과 보기
                </Link>
                <Link href={`/businesses/${business.id}`} className="underline">
                  AI 미리보기(테스트)
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
