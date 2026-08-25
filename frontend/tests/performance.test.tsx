import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { routerMock, getPerformanceMock } = vi.hoisted(() => ({
  routerMock: { push: vi.fn() },
  getPerformanceMock: vi.fn(),
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
    api: { ...actual.api, getPerformance: getPerformanceMock },
  };
});

import PerformancePage from "@/app/businesses/[id]/performance/page";

function makePerformance(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    period: "2026-08",
    ai_response_count: 0,
    ai_response_count_by_agent_type: {},
    coupons_issued: 0,
    coupons_redeemed: 0,
    reservations_this_month: 0,
    recommendation_clicks: 0,
    recommendation_clicks_note: "AI 추천을 보고 우리 가게를 눌러본 횟수예요.",
    visits_confirmed: 0,
    visits_confirmed_note: "쿠폰 사용 처리 또는 예약 방문 완료 처리로 확인된 건수예요.",
    successful_referrals: 0,
    successful_referrals_note: "전체 기간 누적입니다.",
    estimated_time_saved_minutes: 0,
    estimated_time_saved_note: "추정치입니다.",
    revenue_total: "0",
    revenue_direct: "0",
    revenue_assisted: "0",
    revenue_unknown: "0",
    revenue_ai_connected: "0",
    revenue_ai_connected_note: "쿠폰·예약으로 확인된 매출만 합산해요.",
    ...overrides,
  };
}

describe("PerformancePage - 이번 달 우리 가게 성과", () => {
  it("기간을 원본 문자열이 아니라 한국어로 표시하고, 새 필드(관심/방문)를 Funnel에 보여준다", async () => {
    getPerformanceMock.mockResolvedValueOnce(
      makePerformance({
        ai_response_count: 5,
        recommendation_clicks: 3,
        visits_confirmed: 2,
        coupons_issued: 4,
        reservations_this_month: 1,
        revenue_total: "100000",
        revenue_ai_connected: "80000",
        revenue_direct: "50000",
        revenue_assisted: "30000",
        revenue_unknown: "20000",
      })
    );

    render(<PerformancePage />);

    expect(await screen.findByText("2026년 8월 1일 ~ 8월 31일")).toBeInTheDocument();
    expect(screen.queryByText("2026-08")).not.toBeInTheDocument();

    expect(screen.getByText("우리 가게를 눌러본 횟수")).toBeInTheDocument();
    expect(screen.getByText("3회")).toBeInTheDocument();
    expect(screen.getByText("방문 확인")).toBeInTheDocument();
    expect(screen.getByText("2건")).toBeInTheDocument();

    // 전문 용어(DIRECT/ASSISTED/UNKNOWN)가 화면에 그대로 노출되지 않는다.
    expect(screen.queryByText(/DIRECT/)).not.toBeInTheDocument();
    expect(screen.queryByText(/ASSISTED/)).not.toBeInTheDocument();
    expect(screen.queryByText(/UNKNOWN/)).not.toBeInTheDocument();
    expect(screen.getByText("🎟 쿠폰으로 확인된 매출")).toBeInTheDocument();
    expect(screen.getByText("📅 예약으로 확인된 매출")).toBeInTheDocument();
    expect(screen.getByText("🔎 연결 경로를 확인할 수 없는 매출")).toBeInTheDocument();
  });

  it("데이터가 모두 0일 때 빈 카드 대신 다음 행동을 설명하는 문구를 보여준다", async () => {
    getPerformanceMock.mockResolvedValueOnce(makePerformance());

    render(<PerformancePage />);

    await screen.findByText("2026년 8월 1일 ~ 8월 31일");
    expect(
      screen.getByText("아직 기록된 매출이 없어요. 첫 매출이 기록되면 여기에 바로 표시돼요.")
    ).toBeInTheDocument();
    expect(screen.getByText("아직 쿠폰이나 예약으로 이어진 손님이 없어요.")).toBeInTheDocument();
    expect(screen.getByText("아직 방문이 확인되지 않았어요.")).toBeInTheDocument();
  });

  it("지금까지 소개로 가입한 업체는 이번 달 성과와 별개로 전체 기간임을 명시한다", async () => {
    getPerformanceMock.mockResolvedValueOnce(makePerformance({ successful_referrals: 3 }));

    render(<PerformancePage />);

    expect(await screen.findByText("3곳")).toBeInTheDocument();
    expect(screen.getByText(/전체 기간 누적/)).toBeInTheDocument();
  });
});
