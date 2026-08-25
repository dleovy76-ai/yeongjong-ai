import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { routerMock, listCouponsMock, redeemCouponMock, createTransactionMock } = vi.hoisted(() => ({
  routerMock: { push: vi.fn() },
  listCouponsMock: vi.fn(),
  redeemCouponMock: vi.fn(),
  createTransactionMock: vi.fn(),
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
      listCoupons: listCouponsMock,
      redeemCoupon: redeemCouponMock,
      createTransaction: createTransactionMock,
    },
  };
});

import CouponsPage from "@/app/businesses/[id]/coupons/page";

function makeCoupon(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "coupon-1",
    business_id: "biz-1",
    title: "아메리카노 20% 할인",
    description: null,
    discount_type: "PERCENTAGE",
    discount_value: "20",
    start_at: null,
    end_at: null,
    conditions: null,
    usage_limit: null,
    status: "ACTIVE",
    issued_count: 0,
    redeemed_count: 0,
    ...overrides,
  };
}

function makeClaim(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "issue-1",
    coupon_id: "coupon-1",
    code: "HMCARD7Q",
    status: "REDEEMED",
    issued_at: "2026-08-25T00:00:00Z",
    redeemed_at: "2026-08-25T00:00:00Z",
    ...overrides,
  };
}

describe("CouponsPage - 쿠폰 사용 처리와 매출 기록 분리", () => {
  it("쿠폰별 발급/사용 건수를 카드에 보여준다", async () => {
    listCouponsMock.mockResolvedValueOnce([makeCoupon({ issued_count: 24, redeemed_count: 8 })]);

    render(<CouponsPage />);

    expect(await screen.findByText("아메리카노 20% 할인")).toBeInTheDocument();
    expect(screen.getByText("24건")).toBeInTheDocument();
    expect(screen.getByText("8건")).toBeInTheDocument();
  });

  it("쿠폰 사용 처리 직후 매출 입력 카드가 뜨고, 기록하면 금액이 표시된다", async () => {
    listCouponsMock.mockResolvedValueOnce([]);
    redeemCouponMock.mockResolvedValueOnce(makeClaim());
    createTransactionMock.mockResolvedValueOnce({
      id: "txn-1",
      business_id: "biz-1",
      coupon_issue_id: "issue-1",
      reservation_id: null,
      amount: "15000",
      attribution: "DIRECT",
      memo: null,
      occurred_at: "2026-08-25T00:00:00Z",
      created_at: "2026-08-25T00:00:00Z",
    });

    const user = userEvent.setup();
    render(<CouponsPage />);

    await screen.findByText("아직 만든 쿠폰이 없어요. 아래에서 첫 쿠폰을 만들어보세요.");
    await user.type(screen.getByPlaceholderText("예: HMCARD7Q"), "hmcard7q");
    await user.click(screen.getByRole("button", { name: "사용 처리" }));

    expect(redeemCouponMock).toHaveBeenCalledWith("test-token", "biz-1", "hmcard7q");
    expect(await screen.findByText("🎉 쿠폰 사용이 확인됐어요")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("15000"), "15000");
    await user.click(screen.getByRole("button", { name: "매출 기록하기" }));

    expect(createTransactionMock).toHaveBeenCalledWith("test-token", "biz-1", {
      amount: "15000",
      coupon_issue_id: "issue-1",
    });
    expect(await screen.findByText("15,000원")).toBeInTheDocument();
    expect(screen.getByText("매출이 기록됐어요. 쿠폰을 사용한 손님의 매출로 연결됐어요.")).toBeInTheDocument();
  });

  it("나중에를 누르면 Transaction을 만들지 않고, 다시 매출 기록하기를 누르면 입력 폼이 다시 열린다", async () => {
    listCouponsMock.mockResolvedValueOnce([]);
    redeemCouponMock.mockResolvedValueOnce(makeClaim());

    const user = userEvent.setup();
    render(<CouponsPage />);

    await screen.findByText("아직 만든 쿠폰이 없어요. 아래에서 첫 쿠폰을 만들어보세요.");
    await user.type(screen.getByPlaceholderText("예: HMCARD7Q"), "HMCARD7Q");
    await user.click(screen.getByRole("button", { name: "사용 처리" }));

    await screen.findByText("🎉 쿠폰 사용이 확인됐어요");
    await user.click(screen.getByRole("button", { name: "나중에" }));

    expect(createTransactionMock).not.toHaveBeenCalled();
    expect(await screen.findByText("실제 매출: 아직 기록하지 않았어요")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "매출 기록하기" }));
    expect(await screen.findByText("🎉 쿠폰 사용이 확인됐어요")).toBeInTheDocument();
  });
});
