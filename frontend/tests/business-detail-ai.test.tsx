import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { getBusinessMock, getProfileMock, listMenusMock, listCouponsMock, chatMock } = vi.hoisted(() => ({
  getBusinessMock: vi.fn(),
  getProfileMock: vi.fn(),
  listMenusMock: vi.fn(),
  listCouponsMock: vi.fn(),
  chatMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "biz-1" }),
}));

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: null, loading: false }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getBusiness: getBusinessMock,
      getProfile: getProfileMock,
      listMenus: listMenusMock,
      listCoupons: listCouponsMock,
      chat: chatMock,
    },
  };
});

import BusinessDetailPage from "@/app/businesses/[id]/page";

const business = {
  id: "biz-1",
  owner_user_id: "u1",
  name_ko: "영종 식당",
  name_en: null,
  name_zh: null,
  category: "RESTAURANT" as const,
  address: "인천 중구 1",
  phone: null,
  status: "ACTIVE" as const,
  data_source: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("BusinessDetailPage (smoke) - 통합 AI 채팅", () => {
  it("has a single AI chat widget (no separate Chef AI box) that answers both menu and FAQ questions", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    getProfileMock.mockResolvedValueOnce(null);
    listMenusMock.mockResolvedValueOnce([
      {
        id: "m1",
        business_id: "biz-1",
        name: "짜장면",
        description: null,
        price: "8500",
        image_url: "https://example.com/jjajang.jpg",
        is_signature: true,
        allergy_info: null,
        origin_info: null,
        options: null,
      },
    ]);
    listCouponsMock.mockResolvedValueOnce([]);
    chatMock.mockResolvedValueOnce({
      agent_type: "customer",
      reply: "대표 메뉴인 짜장면을 추천드려요!",
      menu_images: [{ id: "m1", name: "짜장면", image_url: "https://example.com/jjajang.jpg" }],
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    expect(await screen.findByText("영종 식당")).toBeInTheDocument();
    expect(screen.queryByText(/Chef AI에게 물어보세요/)).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "전송" })).toHaveLength(1);

    const chatInput = screen.getByPlaceholderText("예: 2명이서 매운 거 먹고 싶어요");
    await user.type(chatInput, "매운 거 추천해줘");
    const chatForm = chatInput.closest("form");
    if (!chatForm) throw new Error("AI chat form not found");
    await user.click(within(chatForm).getByRole("button", { name: "전송" }));

    expect(await screen.findByText("대표 메뉴인 짜장면을 추천드려요!")).toBeInTheDocument();
    expect(chatMock).toHaveBeenCalledWith("biz-1", "매운 거 추천해줘");
    expect(screen.getByAltText("짜장면")).toHaveAttribute("src", "https://example.com/jjajang.jpg");
  });

  it("answers a plain FAQ question through the same widget without attaching any image", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    getProfileMock.mockResolvedValueOnce(null);
    listMenusMock.mockResolvedValueOnce([]);
    listCouponsMock.mockResolvedValueOnce([]);
    chatMock.mockResolvedValueOnce({
      agent_type: "customer",
      reply: "네, 실외석에서는 반려동물과 함께하실 수 있어요.",
      menu_images: [],
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    expect(await screen.findByText("영종 식당")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("예: 2명이서 매운 거 먹고 싶어요"), "강아지 데려가도 되나요?");
    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByText("네, 실외석에서는 반려동물과 함께하실 수 있어요.")).toBeInTheDocument();
    expect(chatMock).toHaveBeenCalledWith("biz-1", "강아지 데려가도 되나요?");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
