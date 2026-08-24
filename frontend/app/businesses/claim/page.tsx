"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError, CATEGORY_LABELS, type Business } from "@/lib/api";

export default function ClaimBusinessPage() {
  return (
    <Suspense fallback={null}>
      <ClaimBusinessPageInner />
    </Suspense>
  );
}

function ClaimBusinessPageInner() {
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("query") ?? "");
  const [results, setResults] = useState<Business[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [claimingId, setClaimingId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    const prefilled = searchParams.get("query");
    if (!token || !prefilled) return;
    api.listUnclaimedBusinesses(prefilled).then(setResults).catch(() => setResults([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      setResults(await api.listUnclaimedBusinesses(query));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "검색 중 오류가 발생했습니다.");
    }
  };

  const onClaim = async (businessId: string) => {
    if (!token) return;
    setClaimingId(businessId);
    setError(null);
    try {
      await api.claimBusiness(token, businessId);
      router.push(`/businesses/${businessId}/menus`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "가게 등록 중 오류가 발생했습니다.");
      setClaimingId(null);
    }
  };

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <h1 className="mb-2 text-2xl font-bold">우리 가게 찾기</h1>
      <p className="mb-8 text-sm text-gray-600">
        영종 AI에 이미 등록되어 있는 가게라면, 새로 만들 필요 없이 여기서 찾아서 내 가게로
        가져올 수 있어요.
      </p>

      <form onSubmit={onSearch} className="mb-6 flex gap-2">
        <input
          className="flex-1 rounded-md border border-gray-300 px-3 py-2"
          placeholder="가게 이름이나 주소로 검색"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="submit" className="rounded-md bg-black px-4 py-2 text-white">
          검색
        </button>
      </form>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {results !== null && (
        <ul className="mb-8 flex flex-col gap-2">
          {results.map((business) => (
            <li
              key={business.id}
              className="flex items-center justify-between rounded-md border border-gray-200 p-3 text-sm"
            >
              <div>
                <p className="font-semibold">{business.name_ko}</p>
                <p className="text-gray-500">
                  {CATEGORY_LABELS[business.category]} · {business.address}
                </p>
              </div>
              <button
                onClick={() => onClaim(business.id)}
                disabled={claimingId === business.id}
                className="rounded-md border border-black px-3 py-1.5 disabled:opacity-50"
              >
                {claimingId === business.id ? "등록 중..." : "내 가게예요"}
              </button>
            </li>
          ))}
          {results.length === 0 && (
            <p className="text-gray-500">일치하는 가게를 찾지 못했어요.</p>
          )}
        </ul>
      )}

      <Link href="/businesses/new" className="text-sm underline">
        찾는 가게가 없어요 — 새로 등록할게요
      </Link>
    </main>
  );
}
