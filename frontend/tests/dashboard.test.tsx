import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const {
  routerMock,
  myBusinessesMock,
  getBusinessPilotDashboardMock,
  getPerformanceMock,
  getOwnerProfileMock,
  listCouponsMock,
} = vi.hoisted(() => ({
  // useEffect의 deps 배열에 router가 들어가므로(app/dashboard/page.tsx), 매
  // 렌더마다 새 객체를 반환하면 deps가 계속 "바뀐 것"으로 보여 effect가
  // 무한히 재실행된다 - 안정된 참조 하나를 계속 반환해야 한다.
  routerMock: { push: vi.fn() },
  myBusinessesMock: vi.fn(),
  getBusinessPilotDashboardMock: vi.fn(),
  getPerformanceMock: vi.fn(),
  getOwnerProfileMock: vi.fn(),
  listCouponsMock: vi.fn(),
}));

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
    api: {
      ...actual.api,
      myBusinesses: myBusinessesMock,
      getBusinessPilotDashboard: getBusinessPilotDashboardMock,
      getPerformance: getPerformanceMock,
      getOwnerProfile: getOwnerProfileMock,
      listCoupons: listCouponsMock,
    },
  };
});

import DashboardPage from "@/app/dashboard/page";

function makeBusiness(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "biz-1",
    owner_user_id: "u1",
    name_ko: "영종 카페",
    name_en: null,
    name_zh: null,
    category: "CAFE",
    address: "인천 중구 1",
    phone: null,
    status: "ACTIVE",
    data_source: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeDashboard(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    business_id: "biz-1",
    business_name: "영종 카페",
    period: "today",
    ai_interactions_total: 0,
    ai_interactions_by_agent: {},
    coupons_issued: 0,
    coupons_redeemed: 0,
    reservations_created: 0,
    reservations_completed: 0,
    visits_confirmed: 0,
    recommendation_clicks: 0,
    funnel: [],
    revenue: {
      total_revenue: "0",
      ai_connected_revenue: "0",
      direct_revenue: "0",
      assisted_revenue: "0",
      unknown_revenue: "0",
      ai_connected_transaction_count: 0,
    },
    agents: [],
    ...overrides,
  };
}

function makePerformance(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    period: "2026-08",
    ai_response_count: 0,
    ai_response_count_by_agent_type: {},
    coupons_issued: 0,
    coupons_redeemed: 0,
    reservations_this_month: 0,
    successful_referrals: 0,
    successful_referrals_note: "",
    estimated_time_saved_minutes: 0,
    estimated_time_saved_note: "",
    revenue_total: "0",
    revenue_direct: "0",
    revenue_assisted: "0",
    revenue_unknown: "0",
    revenue_ai_connected: "0",
    revenue_ai_connected_note: "",
    ...overrides,
  };
}

function makeOwnerProfile(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "profile-1",
    business_id: "biz-1",
    description: "바다 보이는 카페입니다.",
    brand_tone: null,
    opening_hours: { text: "매일 10:00 - 20:00" },
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

describe("DashboardPage (smoke)", () => {
  it("shows an empty-state message when there are no businesses", async () => {
    myBusinessesMock.mockResolvedValueOnce([]);
    render(<DashboardPage />);

    expect(await screen.findByText(/아직 등록한 업체가 없어요/)).toBeInTheDocument();
  });

  it("renders today's AI activity and the customer funnel once loaded", async () => {
    myBusinessesMock.mockResolvedValueOnce([makeBusiness()]);
    getBusinessPilotDashboardMock.mockImplementation((_token: string, _id: string, period: string) =>
      Promise.resolve(
        period === "today"
          ? makeDashboard({ ai_interactions_total: 5, recommendation_clicks: 3, coupons_issued: 2 })
          : makeDashboard({ reservations_created: 4 })
      )
    );
    getPerformanceMock.mockResolvedValueOnce(makePerformance({ revenue_total: "90000", revenue_ai_connected: "50000" }));
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());
    listCouponsMock.mockResolvedValueOnce([{ id: "c1" }]);

    render(<DashboardPage />);

    expect(await screen.findByText("손님이 우리 가게를 만나는 과정")).toBeInTheDocument();
    expect(screen.getByText("영종 카페")).toBeInTheDocument();
    expect(screen.getAllByText("3회").length).toBeGreaterThan(0);
    expect(screen.getByText("50,000원")).toBeInTheDocument();
    expect(screen.getByText("💡 지금 사장님이 할 일")).toBeInTheDocument();
  });

  it("shows a call-to-action when the business is not public", async () => {
    myBusinessesMock.mockResolvedValueOnce([makeBusiness({ status: "DISABLED" })]);
    getBusinessPilotDashboardMock.mockResolvedValue(makeDashboard());
    getPerformanceMock.mockResolvedValueOnce(makePerformance());
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());
    listCouponsMock.mockResolvedValueOnce([]);

    render(<DashboardPage />);

    expect(await screen.findByText("지금 공개하기")).toBeInTheDocument();
    expect(screen.getByText("지금 우리 가게는 손님에게 보이지 않아요.")).toBeInTheDocument();
  });
});
