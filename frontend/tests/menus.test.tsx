import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { routerMock, listMenusMock, createMenuMock } = vi.hoisted(() => ({
  routerMock: { push: vi.fn() },
  listMenusMock: vi.fn(),
  createMenuMock: vi.fn(),
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
    api: { ...actual.api, listMenus: listMenusMock, createMenu: createMenuMock },
  };
});

import MenusPage from "@/app/businesses/[id]/menus/page";

describe("MenusPage (smoke)", () => {
  it("shows an existing menu's photo and allergy info", async () => {
    listMenusMock.mockResolvedValueOnce([
      {
        id: "m1",
        business_id: "biz-1",
        name: "새우튀김",
        description: null,
        price: "7000",
        image_url: "https://example.com/shrimp.jpg",
        is_signature: false,
        allergy_info: "새우, 밀가루 함유",
        options: null,
      },
    ]);

    render(<MenusPage />);

    expect(await screen.findByText(/새우튀김/)).toBeInTheDocument();
    expect(screen.getByText("알레르기: 새우, 밀가루 함유")).toBeInTheDocument();
    expect(screen.getByAltText("새우튀김")).toHaveAttribute("src", "https://example.com/shrimp.jpg");
  });

  it("submits description/image_url/allergy_info along with the new menu", async () => {
    listMenusMock.mockResolvedValueOnce([]);
    createMenuMock.mockResolvedValueOnce({
      id: "m2",
      business_id: "biz-1",
      name: "김치찌개",
      description: "얼큰한 김치찌개",
      price: "9000",
      image_url: "https://example.com/kimchi.jpg",
      is_signature: false,
      allergy_info: null,
      options: null,
    });

    const user = userEvent.setup();
    render(<MenusPage />);

    await screen.findByText("아직 등록된 메뉴가 없어요.");

    await user.type(screen.getByLabelText(/메뉴명/), "김치찌개");
    await user.type(screen.getByLabelText(/가격/), "9000");
    await user.type(screen.getByLabelText(/메뉴 설명/), "얼큰한 김치찌개");
    await user.type(screen.getByLabelText(/사진 URL/), "https://example.com/kimchi.jpg");
    await user.click(screen.getByRole("button", { name: "메뉴 추가" }));

    expect(createMenuMock).toHaveBeenCalledWith("test-token", "biz-1", {
      name: "김치찌개",
      price: "9000",
      is_signature: false,
      description: "얼큰한 김치찌개",
      image_url: "https://example.com/kimchi.jpg",
      allergy_info: undefined,
    });
  });
});
