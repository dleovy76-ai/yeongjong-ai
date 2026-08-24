import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { routerMock, myBusinessesMock } = vi.hoisted(() => ({
  // useEffect의 deps 배열에 router가 들어가므로(app/dashboard/page.tsx), 매
  // 렌더마다 새 객체를 반환하면 deps가 계속 "바뀐 것"으로 보여 effect가
  // 무한히 재실행된다 - 안정된 참조 하나를 계속 반환해야 한다.
  routerMock: { push: vi.fn() },
  myBusinessesMock: vi.fn(),
}));
const pushMock = routerMock.push;

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    token: "test-token",
    user: { id: "u1", email: "owner@example.com", name: "사장", role: "BUSINESS_OWNER", phone: null, locale: "ko" },
    loading: false,
  }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, myBusinesses: myBusinessesMock },
  };
});

import DashboardPage from "@/app/dashboard/page";

describe("DashboardPage (smoke)", () => {
  it("renders the owner's businesses once loaded", async () => {
    myBusinessesMock.mockResolvedValueOnce([
      {
        id: "biz-1",
        owner_user_id: "u1",
        name_ko: "영종 카페",
        name_en: null,
        name_zh: null,
        category: "CAFE",
        address: "인천 중구 1",
        phone: null,
        status: "DRAFT",
        data_source: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ]);

    render(<DashboardPage />);

    expect(await screen.findByText("영종 카페")).toBeInTheDocument();
    expect(screen.getByText("준비 중 (비공개)")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no businesses", async () => {
    myBusinessesMock.mockResolvedValueOnce([]);
    render(<DashboardPage />);

    expect(await screen.findByText(/아직 등록한 업체가 없어요/)).toBeInTheDocument();
  });
});
