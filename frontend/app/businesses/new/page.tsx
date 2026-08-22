"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, type BusinessCategory, ApiError } from "@/lib/api";

const CATEGORY_OPTIONS: { value: BusinessCategory; label: string }[] = [
  { value: "RESTAURANT", label: "음식점" },
  { value: "CAFE", label: "카페" },
  { value: "LODGING", label: "숙박" },
  { value: "EXPERIENCE", label: "체험/관광" },
];

export default function NewBusinessPage() {
  const { token, loading: authLoading } = useAuth();
  const router = useRouter();
  const [nameKo, setNameKo] = useState("");
  const [category, setCategory] = useState<BusinessCategory>("RESTAURANT");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!authLoading && !token) router.push("/login");
  }, [authLoading, token, router]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setSubmitting(true);
    try {
      const business = await api.createBusiness(token, {
        name_ko: nameKo,
        category,
        address,
        phone: phone || undefined,
      });
      router.push(`/businesses/${business.id}/menus`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "업체 등록 중 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto max-w-lg px-6 py-12">
      <p className="mb-1 text-sm text-gray-500">Step 1 / 3 · 업체 정보</p>
      <h1 className="mb-8 text-2xl font-bold">업체를 등록해 주세요</h1>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          업체명 *
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            value={nameKo}
            onChange={(e) => setNameKo(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          업종 *
          <select
            className="rounded-md border border-gray-300 px-3 py-2"
            value={category}
            onChange={(e) => setCategory(e.target.value as BusinessCategory)}
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          주소 *
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            required
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          전화번호
          <input
            className="rounded-md border border-gray-300 px-3 py-2"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "등록 중..." : "다음: 메뉴 등록"}
        </button>
      </form>
    </main>
  );
}
