import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { routerMock, listUnclaimedBusinessesMock, claimBusinessMock } = vi.hoisted(() => ({
  routerMock: { push: vi.fn() },
  listUnclaimedBusinessesMock: vi.fn(),
  claimBusinessMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useSearchParams: () => new URLSearchParams(),
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
      listUnclaimedBusinesses: listUnclaimedBusinessesMock,
      claimBusiness: claimBusinessMock,
    },
  };
});

import ClaimBusinessPage from "@/app/businesses/claim/page";

function makeBusiness(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "biz-1",
    name_ko: "평상집",
    category: "RESTAURANT",
    address: "인천 중구 운서동",
    ...overrides,
  };
}

describe("ClaimBusinessPage - 실시간 자동완성 검색", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("1글자만 입력하면 자동 검색을 호출하지 않는다", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ClaimBusinessPage />);

    await user.type(screen.getByPlaceholderText("가게 이름이나 주소로 검색"), "평");
    await vi.advanceTimersByTimeAsync(500);

    expect(listUnclaimedBusinessesMock).not.toHaveBeenCalled();
  });

  it("2글자 이상 입력하고 잠시 기다리면 자동으로 검색해서 후보를 보여준다", async () => {
    listUnclaimedBusinessesMock.mockResolvedValueOnce([makeBusiness()]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ClaimBusinessPage />);

    await user.type(screen.getByPlaceholderText("가게 이름이나 주소로 검색"), "평상");
    await vi.advanceTimersByTimeAsync(500);

    await waitFor(() => expect(listUnclaimedBusinessesMock).toHaveBeenCalledWith("평상"));
    expect(await screen.findByText("평상집")).toBeInTheDocument();
  });

  it("타이핑 도중에는 마지막 값으로만 한 번 검색한다(디바운스)", async () => {
    listUnclaimedBusinessesMock.mockResolvedValue([]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ClaimBusinessPage />);

    await user.type(screen.getByPlaceholderText("가게 이름이나 주소로 검색"), "평상인");
    await vi.advanceTimersByTimeAsync(500);

    await waitFor(() => expect(listUnclaimedBusinessesMock).toHaveBeenCalledTimes(1));
    expect(listUnclaimedBusinessesMock).toHaveBeenCalledWith("평상인");
  });

  it("검색 결과가 없으면 안내 문구를 보여준다", async () => {
    listUnclaimedBusinessesMock.mockResolvedValueOnce([]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ClaimBusinessPage />);

    await user.type(screen.getByPlaceholderText("가게 이름이나 주소로 검색"), "평상인");
    await vi.advanceTimersByTimeAsync(500);

    expect(await screen.findByText("일치하는 가게를 찾지 못했어요.")).toBeInTheDocument();
  });

  it("검색 버튼을 누르면 디바운스를 기다리지 않고 바로 검색한다", async () => {
    listUnclaimedBusinessesMock.mockResolvedValueOnce([makeBusiness()]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ClaimBusinessPage />);

    await user.type(screen.getByPlaceholderText("가게 이름이나 주소로 검색"), "평상집");
    await user.click(screen.getByRole("button", { name: "검색" }));

    expect(await screen.findByText("평상집")).toBeInTheDocument();
  });

  it("'내 가게예요'를 누르면 사업자 확인 폼이 펼쳐지고, 채우기 전엔 등록 버튼이 비활성화된다", async () => {
    listUnclaimedBusinessesMock.mockResolvedValueOnce([makeBusiness()]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ClaimBusinessPage />);

    await user.type(screen.getByPlaceholderText("가게 이름이나 주소로 검색"), "평상집");
    await vi.advanceTimersByTimeAsync(500);
    await user.click(await screen.findByRole("button", { name: "내 가게예요" }));

    const submitButton = screen.getByRole("button", { name: "확인하고 등록하기" });
    expect(submitButton).toBeDisabled();

    await user.type(screen.getByLabelText("사업자등록번호"), "123-45-67890");
    await user.type(screen.getByLabelText("대표자명"), "김사장");
    expect(submitButton).toBeDisabled();
    await user.type(screen.getByLabelText("개업일자"), "2020-01-01");
    expect(submitButton).toBeEnabled();
  });

  it("사업자 정보를 채우고 등록하면 국세청 확인 후 메뉴 페이지로 이동한다", async () => {
    listUnclaimedBusinessesMock.mockResolvedValueOnce([makeBusiness()]);
    claimBusinessMock.mockResolvedValueOnce(makeBusiness());
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ClaimBusinessPage />);

    await user.type(screen.getByPlaceholderText("가게 이름이나 주소로 검색"), "평상집");
    await vi.advanceTimersByTimeAsync(500);
    await user.click(await screen.findByRole("button", { name: "내 가게예요" }));

    await user.type(screen.getByLabelText("사업자등록번호"), "123-45-67890");
    await user.type(screen.getByLabelText("대표자명"), "김사장");
    await user.type(screen.getByLabelText("개업일자"), "2020-01-01");
    await user.click(screen.getByRole("button", { name: "확인하고 등록하기" }));

    await waitFor(() =>
      expect(claimBusinessMock).toHaveBeenCalledWith("test-token", "biz-1", {
        business_registration_number: "123-45-67890",
        representative_name: "김사장",
        start_date: "2020-01-01",
      })
    );
    expect(routerMock.push).toHaveBeenCalledWith("/businesses/biz-1/menus");
  });

  it("국세청 정보와 일치하지 않으면 에러 메시지를 보여주고 이동하지 않는다", async () => {
    listUnclaimedBusinessesMock.mockResolvedValueOnce([makeBusiness()]);
    claimBusinessMock.mockRejectedValueOnce(
      new (await import("@/lib/api")).ApiError(400, "입력하신 사업자등록번호/대표자명/개업일자가 국세청 정보와 일치하지 않습니다.")
    );
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ClaimBusinessPage />);

    await user.type(screen.getByPlaceholderText("가게 이름이나 주소로 검색"), "평상집");
    await vi.advanceTimersByTimeAsync(500);
    await user.click(await screen.findByRole("button", { name: "내 가게예요" }));

    await user.type(screen.getByLabelText("사업자등록번호"), "999-99-99999");
    await user.type(screen.getByLabelText("대표자명"), "가짜사장");
    await user.type(screen.getByLabelText("개업일자"), "2020-01-01");
    await user.click(screen.getByRole("button", { name: "확인하고 등록하기" }));

    expect(
      await screen.findByText("입력하신 사업자등록번호/대표자명/개업일자가 국세청 정보와 일치하지 않습니다.")
    ).toBeInTheDocument();
    expect(routerMock.push).not.toHaveBeenCalled();
  });
});
