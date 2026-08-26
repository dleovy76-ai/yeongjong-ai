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

  it("후보 목록에서 '내 가게예요'를 누르면 등록하고 메뉴 페이지로 이동한다", async () => {
    listUnclaimedBusinessesMock.mockResolvedValueOnce([makeBusiness()]);
    claimBusinessMock.mockResolvedValueOnce(makeBusiness());
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<ClaimBusinessPage />);

    await user.type(screen.getByPlaceholderText("가게 이름이나 주소로 검색"), "평상집");
    await vi.advanceTimersByTimeAsync(500);

    await user.click(await screen.findByRole("button", { name: "내 가게예요" }));

    await waitFor(() => expect(claimBusinessMock).toHaveBeenCalledWith("test-token", "biz-1"));
    expect(routerMock.push).toHaveBeenCalledWith("/businesses/biz-1/menus");
  });
});
