"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export function NavBar() {
  const { user, logout, loading } = useAuth();

  return (
    <header className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
      <Link href="/" className="font-bold">
        영종 AI
      </Link>
      <nav className="flex items-center gap-4 text-sm">
        {loading ? null : user ? (
          <>
            <Link href="/dashboard">내 업체</Link>
            <span className="text-gray-500">{user.name}님</span>
            <button onClick={logout} className="text-gray-500 underline">
              로그아웃
            </button>
          </>
        ) : (
          <>
            <Link href="/login">로그인</Link>
            <Link href="/register" className="rounded-md bg-black px-3 py-1.5 text-white">
              우리 가게 AI 만들기
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
