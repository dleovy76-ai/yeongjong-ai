"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError, CATEGORY_LABELS, type ReferralJoinInfo } from "@/lib/api";

export default function ReferralJoinPage() {
  const { token } = useParams<{ token: string }>();
  const [info, setInfo] = useState<ReferralJoinInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getReferralJoinInfo(token)
      .then(setInfo)
      .catch((err) => setError(err instanceof ApiError ? err.message : "불러오기 실패"));
  }, [token]);

  return (
    <main className="mx-auto flex min-h-[70vh] max-w-lg flex-col items-center justify-center px-6 py-12 text-center">
      {error && (
        <>
          <p className="mb-4 text-sm text-red-600">{error}</p>
          <Link href="/" className="text-sm underline">
            영종 AI 홈으로
          </Link>
        </>
      )}

      {!error && !info && <p className="text-gray-500">불러오는 중...</p>}

      {info && (
        <>
          <p className="mb-2 text-sm text-gray-500">{info.sender_name}님이 추천했어요</p>
          <h1 className="mb-2 text-2xl font-bold">{info.name_ko}</h1>
          <p className="mb-8 text-sm text-gray-600">
            {CATEGORY_LABELS[info.category]} · {info.address}
          </p>

          {info.is_claimed ? (
            <p className="text-sm text-gray-600">
              이미 영종 AI에 등록된 업체예요. 사장님이시라면 로그인해서 확인해보세요.
            </p>
          ) : (
            <>
              <p className="mb-6 text-sm text-gray-600">
                {info.name_ko} 사장님이신가요? 영종 AI에서 우리 가게 AI 직원을 무료로 만들어보세요.
              </p>
              <Link
                href={`/businesses/claim?query=${encodeURIComponent(info.name_ko)}`}
                className="rounded-md bg-black px-6 py-3 text-white"
              >
                우리 가게 확인하고 AI 만들기
              </Link>
            </>
          )}
        </>
      )}
    </main>
  );
}
