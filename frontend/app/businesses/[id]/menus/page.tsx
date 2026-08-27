"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { api, type Menu, type MenuBulkDraftItem, ApiError } from "@/lib/api";

interface MenuCandidate {
  name: string;
  price: string;
  include: boolean;
  isSignature: boolean;
}

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
  const [originInfo, setOriginInfo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);

  const [pasteText, setPasteText] = useState("");
  const [bulkDrafting, setBulkDrafting] = useState(false);
  const [bulkDraftError, setBulkDraftError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<MenuCandidate[] | null>(null);
  const [bulkAdding, setBulkAdding] = useState(false);
  const [bulkAddError, setBulkAddError] = useState<string | null>(null);

  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);

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
        origin_info: originInfo || undefined,
      });
      setMenus((prev) => [...(prev ?? []), menu]);
      setName("");
      setPrice("");
      setIsSignature(false);
      setDescription("");
      setImageUrl("");
      setAllergyInfo("");
      setOriginInfo("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "메뉴 추가 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  const onDraftDescription = async () => {
    if (!token || !name.trim()) return;
    setDraftError(null);
    setDrafting(true);
    try {
      const draft = await api.draftMenuDescription(token, id, name.trim(), isSignature, originInfo.trim());
      setDescription(draft.description);
    } catch (err) {
      setDraftError(err instanceof ApiError ? err.message : "초안 작성 중 오류가 발생했습니다.");
    } finally {
      setDrafting(false);
    }
  };

  const onExtractMenus = async () => {
    if (!token || !pasteText.trim()) return;
    setBulkDraftError(null);
    setBulkDrafting(true);
    try {
      const { items } = await api.draftMenusFromText(token, id, pasteText.trim());
      setCandidates(
        items.map((item: MenuBulkDraftItem) => ({
          name: item.name,
          price: item.price ?? "",
          include: true,
          isSignature: false,
        }))
      );
    } catch (err) {
      setBulkDraftError(err instanceof ApiError ? err.message : "메뉴 추출 중 오류가 발생했습니다.");
    } finally {
      setBulkDrafting(false);
    }
  };

  const updateCandidate = (index: number, patch: Partial<MenuCandidate>) => {
    setCandidates((prev) => prev?.map((c, i) => (i === index ? { ...c, ...patch } : c)) ?? prev);
  };

  const onAddCandidates = async () => {
    if (!token || !candidates) return;
    setBulkAddError(null);
    setBulkAdding(true);
    const remaining: MenuCandidate[] = [];
    const added: Menu[] = [];
    for (const candidate of candidates) {
      const price = candidate.price.trim();
      if (!candidate.include || !candidate.name.trim() || !price || Number(price) <= 0) {
        remaining.push(candidate);
        continue;
      }
      try {
        added.push(
          await api.createMenu(token, id, {
            name: candidate.name.trim(),
            price,
            is_signature: candidate.isSignature,
          })
        );
      } catch {
        remaining.push(candidate);
      }
    }
    if (added.length > 0) setMenus((prev) => [...(prev ?? []), ...added]);
    if (remaining.length > 0) {
      setCandidates(remaining);
      setBulkAddError("일부 메뉴는 추가하지 못했어요. 이름/가격을 확인하고 다시 시도해주세요.");
    } else {
      setCandidates(null);
      setPasteText("");
    }
    setBulkAdding(false);
  };

  const onDelete = async (menuId: string) => {
    if (!token) return;
    await api.deleteMenu(token, id, menuId);
    setMenus((prev) => prev?.filter((m) => m.id !== menuId) ?? null);
  };

  const onToggleSignature = async (menu: Menu) => {
    if (!token) return;
    setToggleError(null);
    setTogglingId(menu.id);
    try {
      const updated = await api.updateMenu(token, id, menu.id, { is_signature: !menu.is_signature });
      setMenus((prev) => prev?.map((m) => (m.id === menu.id ? updated : m)) ?? null);
    } catch (err) {
      setToggleError(err instanceof ApiError ? err.message : "대표 메뉴 설정 중 오류가 발생했습니다.");
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <p className="mb-1 text-sm text-gray-500">Step 2 / 3 · 메뉴 등록</p>
      <h1 className="mb-2 text-2xl font-bold">메뉴를 등록해 주세요</h1>
      <p className="mb-8 text-sm text-gray-600">
        메뉴를 등록하면 AI가 손님에게 우리 가게의 메뉴를 더 정확하게 소개할 수 있어요.
      </p>

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
                  {menu.origin_info && (
                    <p className="text-xs text-gray-500">재료/원산지: {menu.origin_info}</p>
                  )}
                  {menu.allergy_info && (
                    <p className="text-xs text-gray-500">알레르기: {menu.allergy_info}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => onToggleSignature(menu)}
                  disabled={togglingId === menu.id}
                  className="text-gray-500 underline disabled:opacity-50"
                >
                  {menu.is_signature ? "대표 해제" : "대표로 설정"}
                </button>
                <button onClick={() => onDelete(menu.id)} className="text-gray-500 underline">
                  삭제
                </button>
              </div>
            </li>
          ))}
          {menus.length === 0 && (
            <p className="text-gray-500">
              아직 등록된 메뉴가 없어요. 메뉴를 등록하면 AI가 손님에게 추천할 수 있어요.
            </p>
          )}
        </ul>
      )}
      {toggleError && <p className="mb-8 text-sm text-red-600">{toggleError}</p>}

      <div className="mb-8 flex flex-col gap-3 rounded-md border border-gray-200 p-4">
        <label className="flex flex-col gap-1 text-sm">
          네이버 등에서 복사한 메뉴 붙여넣기 (선택)
          <textarea
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder={"예: 염소탕 15,000원\n염소탕(특) 20,000원"}
            rows={4}
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
          />
        </label>
        <span className="text-xs text-gray-500">
          네이버 플레이스 같은 곳에서 메뉴 목록을 복사해서 붙여넣으면, AI가 메뉴 이름과 가격을
          뽑아드려요. 확인하고 필요하면 고친 뒤에만 실제로 등록돼요.
        </span>
        {bulkDraftError && <p className="text-sm text-red-600">{bulkDraftError}</p>}
        <button
          type="button"
          onClick={onExtractMenus}
          disabled={bulkDrafting || !pasteText.trim()}
          className="self-start rounded-md border border-black px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {bulkDrafting ? "추출 중..." : "메뉴 추출하기"}
        </button>

        {candidates !== null &&
          (candidates.length === 0 ? (
            <p className="text-sm text-gray-500">추출할 수 있는 메뉴를 찾지 못했어요.</p>
          ) : (
            <div className="flex flex-col gap-2 border-t border-gray-200 pt-3">
              <span className="text-xs text-gray-500">
                내용을 확인하고 필요하면 고친 뒤 추가하세요. 가격이 비어있으면 추가되지 않아요.
              </span>
              {candidates.map((candidate, index) => (
                <div key={index} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    aria-label={`${candidate.name || "메뉴"} 포함`}
                    checked={candidate.include}
                    onChange={(e) => updateCandidate(index, { include: e.target.checked })}
                  />
                  <input
                    className="flex-1 rounded-md border border-gray-300 px-2 py-1 text-sm"
                    value={candidate.name}
                    onChange={(e) => updateCandidate(index, { name: e.target.value })}
                  />
                  <input
                    className="w-24 rounded-md border border-gray-300 px-2 py-1 text-sm"
                    placeholder="가격"
                    value={candidate.price}
                    onChange={(e) => updateCandidate(index, { price: e.target.value })}
                  />
                  <span className="text-xs text-gray-500">원</span>
                  <label className="flex items-center gap-1 whitespace-nowrap text-xs text-gray-500">
                    <input
                      type="checkbox"
                      checked={candidate.isSignature}
                      onChange={(e) => updateCandidate(index, { isSignature: e.target.checked })}
                    />
                    대표
                  </label>
                </div>
              ))}
              {bulkAddError && <p className="text-sm text-red-600">{bulkAddError}</p>}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onAddCandidates}
                  disabled={bulkAdding}
                  className="rounded-md bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
                >
                  {bulkAdding ? "추가 중..." : "선택한 메뉴 추가하기"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCandidates(null);
                    setPasteText("");
                  }}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
                >
                  취소
                </button>
              </div>
            </div>
          ))}
      </div>

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
        <div className="flex flex-col gap-1 text-sm">
          <div className="flex items-center justify-between">
            <label htmlFor="menu-description">메뉴 설명 (선택)</label>
            <button
              type="button"
              onClick={onDraftDescription}
              disabled={drafting || !name.trim()}
              className="rounded-md border border-black px-3 py-1 text-xs disabled:opacity-50"
            >
              {drafting ? "작성 중..." : "AI가 초안 써줄게요"}
            </button>
          </div>
          {draftError && <p className="text-sm text-red-600">{draftError}</p>}
          <textarea
            id="menu-description"
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 24시간 우려낸 사골 육수에 얼큰하게 끓인 김치찌개"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <span className="text-xs text-gray-500">
            Chef AI가 손님에게 메뉴를 추천할 때 이 설명을 참고해요. 메뉴명을 먼저 입력하면 AI가 초안을
            써줘요 — 확인하고 자유롭게 고쳐서 저장하세요.
          </span>
        </div>
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
          재료/원산지 (선택)
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            placeholder="예: 인천 앞바다에서 직접 잡은 백합 사용"
            value={originInfo}
            onChange={(e) => setOriginInfo(e.target.value)}
          />
          <span className="text-xs text-gray-500">
            여기 적은 내용만 실제 사실로 취급돼요. 채워두면 AI 초안과 Chef AI 답변에 그대로
            활용돼서 신뢰도를 높여주고, 비워두면 AI는 재료·원산지를 절대 추측해서 말하지 않아요.
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
