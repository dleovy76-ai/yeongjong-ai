import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/lib/api";

const { pushMock, recommendMock, recordRecommendationClickMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  recommendMock: vi.fn(),
  recordRecommendationClickMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      recommend: recommendMock,
      recordRecommendationClick: recordRecommendationClickMock,
    },
  };
});

import DiscoverPage from "@/app/discover/page";

const businessRecommendation = {
  agent_type: "info",
  reply: "바다 전망 카페로는 데모카페C를 추천드려요.",
  interaction_id: "interaction-1",
  recommendations: [
    { id: "biz-1", name: "데모카페C", category: "CAFE", source: "business" as const, reason: "바다가 보여요" },
  ],
};

async function askAndWaitForReply(user: ReturnType<typeof userEvent.setup>, expectedReplyText: string) {
  await user.type(screen.getByPlaceholderText("예: 바다 보이는 카페 가고 싶어"), "바다 보이는 카페");
  await user.click(screen.getByRole("button", { name: "전송" }));
  expect(await screen.findByText(expectedReplyText)).toBeInTheDocument();
}

describe("DiscoverPage (smoke) - Info AI", () => {
  it("renders and returns a recommendation from Info AI", async () => {
    recommendMock.mockResolvedValueOnce({
      agent_type: "info",
      reply: "바다 전망 카페로는 데모카페C를 추천드려요.",
      interaction_id: null,
      recommendations: [],
    });
    const user = userEvent.setup();
    render(<DiscoverPage />);

    expect(screen.getByRole("heading", { name: "영종도에서 뭐 할까?" })).toBeInTheDocument();

    await askAndWaitForReply(user, "바다 전망 카페로는 데모카페C를 추천드려요.");
  });

  it("shows a friendly message when Info AI request fails (API error state)", async () => {
    recommendMock.mockRejectedValueOnce(new ApiError(503, "AI 기능이 아직 설정되지 않았습니다."));
    const user = userEvent.setup();
    render(<DiscoverPage />);

    await user.type(screen.getByPlaceholderText("예: 바다 보이는 카페 가고 싶어"), "아무거나");
    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByText("AI 기능이 아직 설정되지 않았습니다.")).toBeInTheDocument();
  });

  it("renders a recommendation card when the reply includes structured picks", async () => {
    recommendMock.mockResolvedValueOnce(businessRecommendation);
    const user = userEvent.setup();
    render(<DiscoverPage />);

    await askAndWaitForReply(user, businessRecommendation.reply);

    expect(screen.getByText("데모카페C")).toBeInTheDocument();
    expect(screen.getByText("바다가 보여요")).toBeInTheDocument();
  });

  it("records a click and navigates to the business page when a card is clicked", async () => {
    recommendMock.mockResolvedValueOnce(businessRecommendation);
    recordRecommendationClickMock.mockResolvedValueOnce({
      id: "click-1",
      ai_interaction_id: "interaction-1",
      entity_id: "biz-1",
      entity_type: "business",
    });
    const user = userEvent.setup();
    render(<DiscoverPage />);

    await askAndWaitForReply(user, businessRecommendation.reply);
    await user.click(screen.getByText("데모카페C"));

    expect(pushMock).toHaveBeenCalledWith("/businesses/biz-1");
    await waitFor(() =>
      expect(recordRecommendationClickMock).toHaveBeenCalledWith("interaction-1", "biz-1", "business")
    );
  });

  it("still navigates to the business page even when click tracking fails", async () => {
    recommendMock.mockResolvedValueOnce(businessRecommendation);
    recordRecommendationClickMock.mockRejectedValueOnce(new ApiError(500, "기록 실패"));
    const user = userEvent.setup();
    render(<DiscoverPage />);

    await askAndWaitForReply(user, businessRecommendation.reply);
    await user.click(screen.getByText("데모카페C"));

    expect(pushMock).toHaveBeenCalledWith("/businesses/biz-1");
  });

  it("does not call the click API when interaction_id is missing", async () => {
    recommendMock.mockResolvedValueOnce({
      ...businessRecommendation,
      interaction_id: null,
    });
    const user = userEvent.setup();
    render(<DiscoverPage />);

    await askAndWaitForReply(user, businessRecommendation.reply);
    await user.click(screen.getByText("데모카페C"));

    expect(pushMock).toHaveBeenCalledWith("/businesses/biz-1");
    expect(recordRecommendationClickMock).not.toHaveBeenCalled();
  });

  it("debounces repeated clicks on the same recommendation card", async () => {
    recommendMock.mockResolvedValueOnce(businessRecommendation);
    recordRecommendationClickMock.mockResolvedValue({
      id: "click-1",
      ai_interaction_id: "interaction-1",
      entity_id: "biz-1",
      entity_type: "business",
    });
    const user = userEvent.setup();
    render(<DiscoverPage />);

    await askAndWaitForReply(user, businessRecommendation.reply);
    const card = screen.getByText("데모카페C").closest("button");
    if (!card) throw new Error("recommendation card button not found");

    await user.click(card);
    await user.click(card);
    await user.click(card);

    await waitFor(() => expect(recordRecommendationClickMock).toHaveBeenCalledTimes(1));
  });
});
