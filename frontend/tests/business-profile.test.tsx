import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { routerMock, getOwnerProfileMock, updateProfileMock, analyzeExpansionMock } = vi.hoisted(() => ({
  routerMock: { push: vi.fn() },
  getOwnerProfileMock: vi.fn(),
  updateProfileMock: vi.fn(),
  analyzeExpansionMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useParams: () => ({ id: "biz-1" }),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token", loading: false }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getOwnerProfile: getOwnerProfileMock,
      updateProfile: updateProfileMock,
      analyzeExpansion: analyzeExpansionMock,
    },
  };
});

import BusinessProfilePage from "@/app/businesses/[id]/profile/page";

function makeOwnerProfile(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "profile-1",
    business_id: "biz-1",
    description: null,
    brand_tone: null,
    opening_hours: null,
    holiday: null,
    parking: null,
    pet_policy: null,
    reservation_policy: null,
    takeout_policy: null,
    payment_methods: null,
    faq: null,
    naver_place_url: null,
    naver_map_url: null,
    monthly_visitor_estimate: null,
    ...overrides,
  };
}

describe("BusinessProfilePage - P0-3 온보딩 완료 체감 순간", () => {
  it("저장 전에는 완료 카드가 안 뜬다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());

    render(<BusinessProfilePage />);

    expect(await screen.findByText("Step 3 / 3 · AI 정보")).toBeInTheDocument();
    expect(screen.queryByText("🎉 우리 가게 AI가 준비됐어요!")).not.toBeInTheDocument();
  });

  it("저장하면 완료 카드가 뜨고, AI 테스트와 Home 공개 링크가 둘 다 보인다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());
    updateProfileMock.mockResolvedValueOnce(makeOwnerProfile({ description: "설명" }));
    analyzeExpansionMock.mockResolvedValueOnce([]);

    const user = userEvent.setup();
    render(<BusinessProfilePage />);

    await screen.findByText("Step 3 / 3 · AI 정보");
    await user.type(screen.getByLabelText("가게 소개"), "설명");
    await user.click(screen.getByRole("button", { name: "저장하기" }));

    expect(await screen.findByText("🎉 우리 가게 AI가 준비됐어요!")).toBeInTheDocument();

    const testLink = screen.getByRole("link", { name: "AI 테스트해보기 →" });
    expect(testLink).toHaveAttribute("href", "/businesses/biz-1");

    const homeLink = screen.getByRole("link", { name: "Home에서 공개하기 →" });
    expect(homeLink).toHaveAttribute("href", "/dashboard");
  });
});
