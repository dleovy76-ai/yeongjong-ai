import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { getBusinessMock, getProfileMock, listMenusMock, listCouponsMock, chefChatMock } = vi.hoisted(() => ({
  getBusinessMock: vi.fn(),
  getProfileMock: vi.fn(),
  listMenusMock: vi.fn(),
  listCouponsMock: vi.fn(),
  chefChatMock: vi.fn(),
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
      chefChat: chefChatMock,
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

describe("BusinessDetailPage (smoke) - Chef AI", () => {
  it("shows the Chef AI widget once menus load, and it talks to Chef AI", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    getProfileMock.mockResolvedValueOnce(null);
    listMenusMock.mockResolvedValueOnce([
      {
        id: "m1",
        business_id: "biz-1",
        name: "짜장면",
        description: null,
        price: "8500",
        image_url: null,
        is_signature: true,
        allergy_info: null,
        origin_info: null,
        options: null,
      },
    ]);
    listCouponsMock.mockResolvedValueOnce([]);
    chefChatMock.mockResolvedValueOnce({ agent_type: "chef", reply: "대표 메뉴인 짜장면을 추천드려요!" });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    expect(await screen.findByText("영종 식당")).toBeInTheDocument();
    expect(screen.getByText("뭘 먹을지 고민되면 Chef AI에게 물어보세요")).toBeInTheDocument();

    const chefInput = screen.getByPlaceholderText("예: 2명이서 매운 거 먹고 싶어요");
    await user.type(chefInput, "매운 거 추천해줘");
    const chefForm = chefInput.closest("form");
    if (!chefForm) throw new Error("Chef AI form not found");
    await user.click(within(chefForm).getByRole("button", { name: "전송" }));

    expect(await screen.findByText("대표 메뉴인 짜장면을 추천드려요!")).toBeInTheDocument();
    expect(chefChatMock).toHaveBeenCalledWith("biz-1", "매운 거 추천해줘");
  });

  it("shows the real menu photo when Chef AI's reply names a menu with an image", async () => {
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
    chefChatMock.mockResolvedValueOnce({
      agent_type: "chef",
      reply: "대표 메뉴인 짜장면을 추천드려요!",
      menu_images: [{ id: "m1", name: "짜장면", image_url: "https://example.com/jjajang.jpg" }],
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    expect(await screen.findByText("영종 식당")).toBeInTheDocument();
    const chefInput = screen.getByPlaceholderText("예: 2명이서 매운 거 먹고 싶어요");
    await user.type(chefInput, "매운 거 추천해줘");
    const chefForm = chefInput.closest("form");
    if (!chefForm) throw new Error("Chef AI form not found");
    await user.click(within(chefForm).getByRole("button", { name: "전송" }));

    const photo = await screen.findByAltText("짜장면");
    expect(photo).toHaveAttribute("src", "https://example.com/jjajang.jpg");
  });
});
