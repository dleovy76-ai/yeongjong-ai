"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api, type Menu, ApiError } from "@/lib/api";

export default function MenusPage() {
  const { id } = useParams<{ id: string }>();
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();

  const [menus, setMenus] = useState<Menu[] | null>(null);
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [isSignature, setIsSignature] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  useEffect(() => {
    api.listMenus(id).then(setMenus).catch(() => setMenus([]));
  }, [id]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setSubmitting(true);
    try {
      const menu = await api.createMenu(token, id, { name, price, is_signature: isSignature });
      setMenus((prev) => [...(prev ?? []), menu]);
      setName("");
      setPrice("");
      setIsSignature(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "메뉴 추가 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = async (menuId: string) => {
    if (!token) return;
    await api.deleteMenu(token, id, menuId);
    setMenus((prev) => prev?.filter((m) => m.id !== menuId) ?? null);
  };

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <p className="mb-1 text-sm text-gray-500">Step 2 / 3 · 메뉴 등록</p>
      <h1 className="mb-8 text-2xl font-bold">메뉴를 등록해 주세요</h1>

      {menus === null ? (
        <p className="text-gray-500">불러오는 중...</p>
      ) : (
        <ul className="mb-8 flex flex-col gap-2">
          {menus.map((menu) => (
            <li
              key={menu.id}
              className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2 text-sm"
            >
              <span>
                {menu.is_signature && "⭐ "}
                {menu.name} — {Number(menu.price).toLocaleString()}원
              </span>
              <button onClick={() => onDelete(menu.id)} className="text-gray-500 underline">
                삭제
              </button>
            </li>
          ))}
          {menus.length === 0 && <p className="text-gray-500">아직 등록된 메뉴가 없어요.</p>}
        </ul>
      )}

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          메뉴명 *
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          가격 (원) *
          <input
            type="number"
            min="0"
            step="1"
            className="rounded-md border border-gray-300 px-3 py-2"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            required
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isSignature}
            onChange={(e) => setIsSignature(e.target.checked)}
          />
          대표 메뉴예요
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "추가 중..." : "메뉴 추가"}
        </button>
      </form>

      <Link
        href={`/businesses/${id}/profile`}
        className="mt-8 inline-block rounded-md border border-black px-4 py-2 text-center"
      >
        다음: AI 정보 입력 →
      </Link>
    </main>
  );
}
