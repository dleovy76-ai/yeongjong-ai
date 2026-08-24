import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { pushMock, getAdminPilotOverviewMock, updatePilotStatusMock, downloadPilotCsvMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  getAdminPilotOverviewMock: vi.fn(),
  updatePilotStatusMock: vi.fn(),
  downloadPilotCsvMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    token: "admin-token",
    user: { id: "u1", email: "admin@example.com", name: "운영자", role: "ADMIN", phone: null, locale: "ko" },
    loading: false,
  }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getAdminPilotOverview: getAdminPilotOverviewMock,
      updatePilotStatus: updatePilotStatusMock,
      downloadPilotCsv: downloadPilotCsvMock,
    },
  };
});

import AdminPilotDashboardPage from "@/app/admin/pilot/page";

const emptyOverview = {
  period: "30d",
  pilot_business_count: 0,
  active_business_count: 0,
  daily_active_businesses: 0,
  weekly_active_businesses: 0,
  businesses_using_ai: 0,
  customer_ai_questions: 0,
  chef_ai_questions: 0,
  info_ai_questions: 0,
  recommendation_impressions: 0,
  recommendation_clicks: 0,
  coupons_issued: 0,
  coupons_redeemed: 0,
  reservations_created: 0,
  reservations_completed: 0,
  visits_confirmed: 0,
  transactions_created: 0,
  revenue: {
    total_revenue: "0",
    ai_connected_revenue: "0",
    direct_revenue: "0",
    assisted_revenue: "0",
    unknown_revenue: "0",
    ai_connected_transaction_count: 0,
  },
  revenue_by_business: {},
  expansion_runs: 0,
  partner_candidates: 0,
  partner_invites: 0,
  referral_clicks: 0,
  new_businesses_via_referral: 0,
  funnel: [],
  businesses: [],
};

const overviewWithData = {
  ...emptyOverview,
  pilot_business_count: 1,
  active_business_count: 1,
  revenue: { ...emptyOverview.revenue, ai_connected_revenue: "77000.00", total_revenue: "90000.00" },
  funnel: [{ key: "ai_questions", label: "AI 질문", count: 10, conversion_rate_from_previous: null }],
  businesses: [
    {
      business_id: "biz-1",
      business_name: "영종면옥",
      pilot_status: "PILOT_ACTIVE" as const,
      ai_interactions: 10,
      recommendation_clicks: 3,
      coupons_issued: 2,
      reservations_created: 1,
      visits_confirmed: 1,
      transactions: 1,
      direct_revenue: "50000.00",
      assisted_revenue: "0",
      unknown_revenue: "10000.00",
      ai_connected_revenue: "50000.00",
    },
  ],
};

describe("AdminPilotDashboardPage (smoke)", () => {
  it("shows an empty-state hint when no businesses are pilot-tagged", async () => {
    getAdminPilotOverviewMock.mockResolvedValueOnce(emptyOverview);
    render(<AdminPilotDashboardPage />);

    expect(await screen.findByText(/아직 Pilot 상태로 지정된 업체가 없습니다/)).toBeInTheDocument();
  });

  it("renders funnel, revenue, and the business comparison table when data exists", async () => {
    getAdminPilotOverviewMock.mockResolvedValueOnce(overviewWithData);
    render(<AdminPilotDashboardPage />);

    expect(await screen.findByText("영종면옥")).toBeInTheDocument();
    expect(screen.getByText("77,000원")).toBeInTheDocument();
    expect(screen.getByText("50,000원")).toBeInTheDocument();
  });

  it("changes a business's pilot status and reloads the overview", async () => {
    getAdminPilotOverviewMock.mockResolvedValueOnce(overviewWithData).mockResolvedValueOnce(overviewWithData);
    updatePilotStatusMock.mockResolvedValueOnce({});
    const user = userEvent.setup();
    render(<AdminPilotDashboardPage />);

    await screen.findByText("영종면옥");
    const select = screen.getByDisplayValue("파일럿 진행 중");
    await user.selectOptions(select, "파일럿 종료");

    await waitFor(() =>
      expect(updatePilotStatusMock).toHaveBeenCalledWith("admin-token", "biz-1", "PILOT_COMPLETED")
    );
  });

  it("triggers a CSV download", async () => {
    getAdminPilotOverviewMock.mockResolvedValueOnce(overviewWithData);
    downloadPilotCsvMock.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    render(<AdminPilotDashboardPage />);

    await screen.findByText("영종면옥");
    await user.click(screen.getByRole("button", { name: "CSV 다운로드" }));

    await waitFor(() => expect(downloadPilotCsvMock).toHaveBeenCalledWith("admin-token", "30d"));
  });
});
