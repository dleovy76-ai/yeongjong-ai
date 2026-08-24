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
  const [description, setDescription] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [allergyInfo, setAllergyInfo] = useState("");
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
      const menu = await api.createMenu(token, id, {
        name,
        price,
        is_signature: isSignature,
        description: description || undefined,
        image_url: imageUrl || undefined,
        allergy_info: allergyInfo || undefined,
      });
      setMenus((prev) => [...(prev ?? []), menu]);
      setName("");
      setPrice("");
      setIsSignature(false);
      setDescription("");
      setImageUrl("");
      setAllergyInfo("");
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
              <div className="flex items-center gap-3">
                {menu.image_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={menu.image_url}
                    alt={menu.name}
                    className="h-12 w-12 rounded-md border border-gray-200 object-cover"
                  />
                )}
                <div>
                  <span>
                    {menu.is_signature && "⭐ "}
                    {menu.name} — {Number(menu.price).toLocaleString()}원
                  </span>
                  {menu.allergy_info && (
                    <p className="text-xs text-gray-500">알레르기: {menu.allergy_info}</p>
                  )}
                </div>
              </div>
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
        <label className="flex flex-col gap-1 text-sm">
          메뉴 설명 (선택)
          <textarea
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 24시간 우려낸 사골 육수에 얼큰하게 끓인 김치찌개"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <span className="text-xs text-gray-500">Chef AI가 손님에게 메뉴를 추천할 때 이 설명을 참고해요.</span>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          사진 URL (선택)
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 인스타그램·블로그에 이미 올려둔 사진 링크"
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
          />
          <span className="text-xs text-gray-500">
            새로 업로드하는 게 아니라, 이미 어딘가에 올려둔 사진의 링크를 붙여넣는 거예요. 붙여넣으면
            Chef AI가 이 메뉴를 추천할 때 손님에게 사진도 같이 보여줘요.
          </span>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          알레르기 정보 (선택)
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 새우, 밀가루 함유"
            value={allergyInfo}
            onChange={(e) => setAllergyInfo(e.target.value)}
          />
          <span className="text-xs text-gray-500">
            비워두면 Chef AI는 손님이 알레르기를 물어봤을 때 "확인이 필요합니다"라고 답해요.
          </span>
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
