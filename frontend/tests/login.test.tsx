import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api";

const { pushMock, loginMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  loginMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ login: loginMock }),
}));

import LoginPage from "@/app/login/page";

describe("LoginPage (smoke)", () => {
  it("renders the login form", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: "로그인" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "로그인" })).toBeInTheDocument();
  });

  it("logs in and redirects to the dashboard on success", async () => {
    loginMock.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("이메일"), "owner@example.com");
    await user.type(screen.getByLabelText("비밀번호"), "password123");
    await user.click(screen.getByRole("button", { name: "로그인" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
  });

  it("shows the API error message when login fails (API error state)", async () => {
    loginMock.mockRejectedValueOnce(new ApiError(401, "이메일 또는 비밀번호가 올바르지 않습니다."));
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("이메일"), "owner@example.com");
    await user.type(screen.getByLabelText("비밀번호"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "로그인" }));

    expect(await screen.findByText("이메일 또는 비밀번호가 올바르지 않습니다.")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
