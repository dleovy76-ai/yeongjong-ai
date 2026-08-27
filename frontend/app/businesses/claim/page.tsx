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

const _MIN_QUERY_LENGTH = 2;
const _DEBOUNCE_MS = 300;

function ClaimBusinessPageInner() {
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("query") ?? "");
  const [results, setResults] = useState<Business[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [claimingId, setClaimingId] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [bizNo, setBizNo] = useState("");
  const [repName, setRepName] = useState("");
  const [startDate, setStartDate] = useState("");

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  // 실시간(자동) 검색 - 이름을 완벽히 몰라도 몇 글자만 입력하면 잠시 후
  // 자동으로 후보가 뜬다. 백엔드는 이미 부분(포함) 일치 검색이라
  // (routers/businesses.py list_unclaimed_businesses), 프론트에서 "언제
  // 호출할지"만 바꾸면 된다 - 디바운스는 매 타이핑마다 요청을 보내지 않기
  // 위한 것.
  useEffect(() => {
    if (!token) return;
    const trimmed = query.trim();
    if (trimmed.length < _MIN_QUERY_LENGTH) {
      setResults(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timeoutId = setTimeout(() => {
      api
        .listUnclaimedBusinesses(trimmed)
        .then(setResults)
        .catch((err) => setError(err instanceof ApiError ? err.message : "검색 중 오류가 발생했습니다."))
        .finally(() => setSearching(false));
    }, _DEBOUNCE_MS);
    return () => clearTimeout(timeoutId);
  }, [token, query]);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (trimmed.length < _MIN_QUERY_LENGTH) return;
    setError(null);
    setSearching(true);
    try {
      setResults(await api.listUnclaimedBusinesses(trimmed));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "검색 중 오류가 발생했습니다.");
    } finally {
      setSearching(false);
    }
  };

  const onStartClaim = (businessId: string) => {
    setExpandedId(businessId);
    setError(null);
    setBizNo("");
    setRepName("");
    setStartDate("");
  };

  const onClaim = async (businessId: string) => {
    if (!token) return;
    setClaimingId(businessId);
    setError(null);
    try {
      await api.claimBusiness(token, businessId, {
        business_registration_number: bizNo,
        representative_name: repName,
        start_date: startDate,
      });
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
            <li key={business.id} className="rounded-md border border-gray-200 p-3 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold">{business.name_ko}</p>
                  <p className="text-gray-500">
                    {CATEGORY_LABELS[business.category]} · {business.address}
                  </p>
                </div>
                {expandedId !== business.id && (
                  <button
                    onClick={() => onStartClaim(business.id)}
                    className="rounded-md border border-black px-3 py-1.5"
                  >
                    내 가게예요
                  </button>
                )}
              </div>

              {expandedId === business.id && (
                <div className="mt-3 flex flex-col gap-2 border-t border-gray-200 pt-3">
                  <p className="text-xs text-gray-500">
                    실제 사업자등록 정보를 국세청에서 확인한 뒤에만 등록돼요 — 타인이 무단으로
                    다른 사람의 업체를 가져가는 것을 막기 위해서예요.
                  </p>
                  <label className="flex flex-col gap-1 text-xs">
                    사업자등록번호
                    <input
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                      placeholder="예: 123-45-67890"
                      value={bizNo}
                      onChange={(e) => setBizNo(e.target.value)}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-xs">
                    대표자명
                    <input
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                      value={repName}
                      onChange={(e) => setRepName(e.target.value)}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-xs">
                    개업일자
                    <input
                      className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                      placeholder="예: 2020-01-01"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                    />
                  </label>
                  <div className="mt-1 flex gap-2">
                    <button
                      onClick={() => onClaim(business.id)}
                      disabled={
                        claimingId === business.id || !bizNo.trim() || !repName.trim() || !startDate.trim()
                      }
                      className="rounded-md bg-black px-3 py-1.5 text-white disabled:opacity-50"
                    >
                      {claimingId === business.id ? "확인 중..." : "확인하고 등록하기"}
                    </button>
                    <button
                      onClick={() => setExpandedId(null)}
                      className="rounded-md border border-gray-300 px-3 py-1.5"
                    >
                      취소
                    </button>
                  </div>
                </div>
              )}
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
