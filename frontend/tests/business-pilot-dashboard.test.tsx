import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { pushMock, getBusinessPilotDashboardMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  getBusinessPilotDashboardMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useParams: () => ({ id: "biz-1" }),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "test-token", loading: false }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, getBusinessPilotDashboard: getBusinessPilotDashboardMock },
  };
});

import BusinessPilotDashboardPage from "@/app/businesses/[id]/pilot/page";

const dashboardFixture = {
  business_id: "biz-1",
  business_name: "영종 카페",
  period: "30d",
  ai_interactions_total: 42,
  ai_interactions_by_agent: { customer: 30, chef: 12 },
  coupons_issued: 10,
  coupons_redeemed: 4,
  reservations_created: 3,
  reservations_completed: 2,
  visits_confirmed: 6,
  recommendation_clicks: 5,
  funnel: [
    { key: "ai_questions", label: "AI 질문", count: 42, conversion_rate_from_previous: null },
    { key: "impressions", label: "추천 노출", count: 5, conversion_rate_from_previous: 0.119 },
    { key: "clicks", label: "추천 클릭", count: 5, conversion_rate_from_previous: 1.0 },
    { key: "coupon_or_reservation", label: "쿠폰/예약", count: 13, conversion_rate_from_previous: 2.6 },
    { key: "visits", label: "방문", count: 6, conversion_rate_from_previous: 0.4615 },
    { key: "transactions", label: "거래", count: 3, conversion_rate_from_previous: 0.5 },
  ],
  revenue: {
    total_revenue: "150000.00",
    ai_connected_revenue: "120000.00",
    direct_revenue: "80000.00",
    assisted_revenue: "40000.00",
    unknown_revenue: "30000.00",
    ai_connected_transaction_count: 3,
  },
  agents: [
    { agent_type: "customer", interactions: 30, recommendation_clicks: null, note: null },
    { agent_type: "info", interactions: null, recommendation_clicks: 5, note: "업체별 노출 집계 불가" },
  ],
};

describe("BusinessPilotDashboardPage (smoke)", () => {
  it("renders funnel and revenue once the dashboard loads", async () => {
    getBusinessPilotDashboardMock.mockResolvedValueOnce(dashboardFixture);
    render(<BusinessPilotDashboardPage />);

    expect(await screen.findByText("영종 카페에서 AI가 실제로 얼마나 쓰이고 매출로 이어졌는지 봅니다.", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("AI 질문")).toBeInTheDocument();
    expect(screen.getByText("120,000원")).toBeInTheDocument();
    expect(getBusinessPilotDashboardMock).toHaveBeenCalledWith("test-token", "biz-1", "30d");
  });

  it("reloads the dashboard when a different period is selected", async () => {
    getBusinessPilotDashboardMock.mockResolvedValue(dashboardFixture);
    const user = userEvent.setup();
    render(<BusinessPilotDashboardPage />);

    await screen.findByText("AI 질문");
    await user.click(screen.getByRole("button", { name: "오늘" }));

    await waitFor(() =>
      expect(getBusinessPilotDashboardMock).toHaveBeenCalledWith("test-token", "biz-1", "today")
    );
  });
});
