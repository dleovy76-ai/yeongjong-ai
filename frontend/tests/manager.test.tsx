import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { routerMock, authStateRef, managerChatMock } = vi.hoisted(() => ({
  // 안정된 router 참조를 반환해야 한다 - useEffect deps에 router가 들어가는
  // 페이지에서 매번 새 객체를 주면 effect가 무한 재실행된다.
  routerMock: { push: vi.fn() },
  authStateRef: { current: { token: "test-token" as string | null, loading: false } },
  managerChatMock: vi.fn(),
}));
const pushMock = routerMock.push;

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useParams: () => ({ id: "biz-1" }),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => authStateRef.current,
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, managerChat: managerChatMock },
  };
});

import ManagerChatPage from "@/app/businesses/[id]/manager/page";

describe("ManagerChatPage (smoke) - 사장님 AI", () => {
  it("renders the chat UI and sends a message through Manager AI", async () => {
    authStateRef.current = { token: "test-token", loading: false };
    managerChatMock.mockResolvedValueOnce({ agent_type: "manager", reply: "이번 달 매출은 아직 기록이 없어요." });

    const user = userEvent.setup();
    render(<ManagerChatPage />);

    expect(screen.getByRole("heading", { name: "AI 직원에게 물어보기" })).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("예: 손님 좀 늘려줘"), "이번 달 어때?");
    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByText("이번 달 매출은 아직 기록이 없어요.")).toBeInTheDocument();
    expect(managerChatMock).toHaveBeenCalledWith("test-token", "biz-1", "이번 달 어때?");
  });

  it("redirects to /login when the session has no token (인증 만료 상태)", () => {
    authStateRef.current = { token: null, loading: false };
    render(<ManagerChatPage />);

    expect(pushMock).toHaveBeenCalledWith("/login");
  });
});
