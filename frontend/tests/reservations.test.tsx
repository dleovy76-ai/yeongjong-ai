import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { routerMock, listReservationsMock, listTransactionsMock, updateReservationStatusMock, createTransactionMock } =
  vi.hoisted(() => ({
    routerMock: { push: vi.fn() },
    listReservationsMock: vi.fn(),
    listTransactionsMock: vi.fn(),
    updateReservationStatusMock: vi.fn(),
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
      listReservations: listReservationsMock,
      listTransactions: listTransactionsMock,
      updateReservationStatus: updateReservationStatusMock,
      createTransaction: createTransactionMock,
    },
  };
});

import ReservationsPage from "@/app/businesses/[id]/reservations/page";

function makeReservation(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "resv-1",
    business_id: "biz-1",
    customer_name: "김방문",
    customer_phone: "010-1234-5678",
    reservation_time: "2026-08-30T19:00:00+09:00",
    party_size: 2,
    notes: null,
    status: "CONFIRMED",
    created_at: "2026-08-25T00:00:00Z",
    ...overrides,
  };
}

describe("ReservationsPage - 방문 완료 후 매출 기록", () => {
  it("방문 완료 처리 직후 매출 입력 카드가 자동으로 열리고, 기록하면 실제 매출로 표시된다", async () => {
    listReservationsMock.mockResolvedValueOnce([makeReservation()]);
    listTransactionsMock.mockResolvedValueOnce([]);
    const completed = makeReservation({ status: "COMPLETED" });
    updateReservationStatusMock.mockResolvedValueOnce(completed);
    createTransactionMock.mockResolvedValueOnce({
      id: "txn-1",
      business_id: "biz-1",
      coupon_issue_id: null,
      reservation_id: "resv-1",
      amount: "50000",
      attribution: "ASSISTED",
      memo: null,
      occurred_at: "2026-08-25T00:00:00Z",
      created_at: "2026-08-25T00:00:00Z",
    });

    const user = userEvent.setup();
    render(<ReservationsPage />);

    await screen.findByText(/김방문/);
    await user.click(screen.getByRole("button", { name: "방문 완료 처리" }));

    expect(updateReservationStatusMock).toHaveBeenCalledWith("test-token", "biz-1", "resv-1", "COMPLETED");
    expect(await screen.findByText("🎉 방문이 확인됐어요")).toBeInTheDocument();

    const amountInput = screen.getByPlaceholderText("50000");
    await user.type(amountInput, "50000");
    await user.click(screen.getByRole("button", { name: "매출 기록하기" }));

    expect(createTransactionMock).toHaveBeenCalledWith("test-token", "biz-1", {
      amount: "50000",
      reservation_id: "resv-1",
    });
    expect(await screen.findByText("50,000원")).toBeInTheDocument();
    expect(
      screen.getByText("매출이 기록됐어요. 예약을 통해 방문한 손님의 매출로 연결됐어요.")
    ).toBeInTheDocument();
  });

  it("나중에를 누르면 Transaction을 만들지 않고 방문 완료 상태만 유지된다", async () => {
    listReservationsMock.mockResolvedValueOnce([makeReservation()]);
    listTransactionsMock.mockResolvedValueOnce([]);
    updateReservationStatusMock.mockResolvedValueOnce(makeReservation({ status: "COMPLETED" }));

    const user = userEvent.setup();
    render(<ReservationsPage />);

    await screen.findByText(/김방문/);
    await user.click(screen.getByRole("button", { name: "방문 완료 처리" }));

    await screen.findByText("🎉 방문이 확인됐어요");
    await user.click(screen.getByRole("button", { name: "나중에" }));

    expect(createTransactionMock).not.toHaveBeenCalled();
    expect(await screen.findByText("실제 매출: 아직 기록하지 않았어요")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "매출 기록하기" })).toBeInTheDocument();
  });

  it("이미 매출이 기록된 방문 완료 예약은 입력 폼 없이 금액만 보여준다", async () => {
    listReservationsMock.mockResolvedValueOnce([makeReservation({ status: "COMPLETED" })]);
    listTransactionsMock.mockResolvedValueOnce([
      {
        id: "txn-1",
        business_id: "biz-1",
        coupon_issue_id: null,
        reservation_id: "resv-1",
        amount: "50000",
        attribution: "ASSISTED",
        memo: null,
        occurred_at: "2026-08-25T00:00:00Z",
        created_at: "2026-08-25T00:00:00Z",
      },
    ]);

    render(<ReservationsPage />);

    await screen.findByText(/김방문/);
    expect(screen.getByText("50,000원")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "매출 기록하기" })).not.toBeInTheDocument();
    expect(screen.queryByText("🎉 방문이 확인됐어요")).not.toBeInTheDocument();
  });
});
