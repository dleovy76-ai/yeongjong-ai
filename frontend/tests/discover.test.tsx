import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api";

const { recommendMock } = vi.hoisted(() => ({ recommendMock: vi.fn() }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, recommend: recommendMock },
  };
});

import DiscoverPage from "@/app/discover/page";

describe("DiscoverPage (smoke) - Info AI", () => {
  it("renders and returns a recommendation from Info AI", async () => {
    recommendMock.mockResolvedValueOnce({ agent_type: "info", reply: "바다 전망 카페로는 데모카페C를 추천드려요." });
    const user = userEvent.setup();
    render(<DiscoverPage />);

    expect(screen.getByRole("heading", { name: "영종도에서 뭐 할까?" })).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("예: 바다 보이는 카페 가고 싶어"), "바다 보이는 카페");
    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByText("바다 전망 카페로는 데모카페C를 추천드려요.")).toBeInTheDocument();
  });

  it("shows a friendly message when Info AI request fails (API error state)", async () => {
    recommendMock.mockRejectedValueOnce(new ApiError(503, "AI 기능이 아직 설정되지 않았습니다."));
    const user = userEvent.setup();
    render(<DiscoverPage />);

    await user.type(screen.getByPlaceholderText("예: 바다 보이는 카페 가고 싶어"), "아무거나");
    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByText("AI 기능이 아직 설정되지 않았습니다.")).toBeInTheDocument();
  });
});
