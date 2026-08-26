"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export function NavBar() {
  const { user, logout, loading } = useAuth();

  return (
    <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-ink/10 px-4 py-3 sm:px-6 sm:py-4">
      <Link href="/" className="break-keep font-display text-base text-coral-dark sm:text-lg">
        영종 AI
      </Link>
      <nav className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs sm:gap-x-4 sm:text-sm">
        <Link href="/discover" className="break-keep">
          영종도에서 뭐 할까?
        </Link>
        {loading ? null : user ? (
          <>
            <Link href="/dashboard" className="break-keep">
              내 업체
            </Link>
            <Link href="/me/history" className="break-keep">
              내 이력
            </Link>
            {user.role === "ADMIN" && (
              <Link href="/admin" className="break-keep">
                관리자
              </Link>
            )}
            <span className="break-keep text-gray-500">{user.name}님</span>
            <button onClick={logout} className="break-keep text-gray-500 underline">
              로그아웃
            </button>
          </>
        ) : (
          <>
            <Link href="/login" className="break-keep">
              로그인
            </Link>
            <Link
              href="/register"
              className="break-keep rounded-full bg-coral px-3 py-1.5 font-medium text-white shadow-sm sm:px-4 sm:py-2"
            >
              우리 가게 AI 만들기
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
