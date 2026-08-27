import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  routerMock,
  listMenusMock,
  createMenuMock,
  draftMenuDescriptionMock,
  draftMenusFromTextMock,
  draftMenusFromImageMock,
  updateMenuMock,
} = vi.hoisted(() => ({
  routerMock: { push: vi.fn() },
  listMenusMock: vi.fn(),
  createMenuMock: vi.fn(),
  draftMenuDescriptionMock: vi.fn(),
  draftMenusFromTextMock: vi.fn(),
  draftMenusFromImageMock: vi.fn(),
  updateMenuMock: vi.fn(),
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
      listMenus: listMenusMock,
      createMenu: createMenuMock,
      draftMenuDescription: draftMenuDescriptionMock,
      draftMenusFromText: draftMenusFromTextMock,
      draftMenusFromImage: draftMenusFromImageMock,
      updateMenu: updateMenuMock,
    },
  };
});

import MenusPage from "@/app/businesses/[id]/menus/page";

describe("MenusPage (smoke)", () => {
  it("explains why menus matter to AI recommendations, and the 0-menu state explains the same thing", async () => {
    listMenusMock.mockResolvedValueOnce([]);

    render(<MenusPage />);

    expect(
      await screen.findByText("메뉴를 등록하면 AI가 손님에게 우리 가게의 메뉴를 더 정확하게 소개할 수 있어요.")
    ).toBeInTheDocument();
    expect(
      screen.getByText("아직 등록된 메뉴가 없어요. 메뉴를 등록하면 AI가 손님에게 추천할 수 있어요.")
    ).toBeInTheDocument();
  });

  it("shows an existing menu's photo, origin, and allergy info", async () => {
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
        origin_info: "국내산 새우 사용",
        options: null,
      },
    ]);

    render(<MenusPage />);

    expect(await screen.findByText(/새우튀김/)).toBeInTheDocument();
    expect(screen.getByText("재료/원산지: 국내산 새우 사용")).toBeInTheDocument();
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
      origin_info: null,
      options: null,
    });

    const user = userEvent.setup();
    render(<MenusPage />);

    await screen.findByText(/아직 등록된 메뉴가 없어요/);

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
      origin_info: undefined,
    });
  });

  it("'재료에서 채워줄게요'를 누르면 재료/원산지에서 알레르기 정보를 채운다", async () => {
    listMenusMock.mockResolvedValueOnce([]);

    const user = userEvent.setup();
    render(<MenusPage />);

    await screen.findByText(/아직 등록된 메뉴가 없어요/);

    const fillButton = screen.getByRole("button", { name: "재료에서 채워줄게요" });
    expect(fillButton).toBeDisabled();

    await user.type(screen.getByLabelText(/재료\/원산지/), "새우와 밀가루를 사용한 튀김");
    expect(fillButton).toBeEnabled();
    await user.click(fillButton);

    expect(screen.getByLabelText("알레르기 정보 (선택)")).toHaveValue("새우, 밀");
  });

  it("fills the description field with an AI draft based on the typed menu name", async () => {
    listMenusMock.mockResolvedValueOnce([]);
    draftMenuDescriptionMock.mockResolvedValueOnce({
      description: "얼큰한 김치와 돼지고기를 함께 끓인 찌개예요.",
    });

    const user = userEvent.setup();
    render(<MenusPage />);

    await screen.findByText(/아직 등록된 메뉴가 없어요/);

    const draftButton = screen.getByRole("button", { name: "AI가 초안 써줄게요" });
    expect(draftButton).toBeDisabled();

    await user.type(screen.getByLabelText(/메뉴명/), "김치찌개");
    expect(draftButton).toBeEnabled();
    await user.click(draftButton);

    expect(draftMenuDescriptionMock).toHaveBeenCalledWith("test-token", "biz-1", "김치찌개", false, "");
    expect(await screen.findByDisplayValue("얼큰한 김치와 돼지고기를 함께 끓인 찌개예요.")).toBeInTheDocument();
  });

  it("붙여넣은 텍스트에서 추출한 메뉴 후보를 보여주고, 선택한 항목만 등록한다", async () => {
    listMenusMock.mockResolvedValueOnce([]);
    draftMenusFromTextMock.mockResolvedValueOnce({
      items: [
        { name: "염소탕", price: "15000" },
        { name: "염소탕(특)", price: "20000" },
      ],
    });
    createMenuMock.mockResolvedValueOnce({
      id: "m3",
      business_id: "biz-1",
      name: "염소탕",
      description: null,
      price: "15000",
      image_url: null,
      is_signature: false,
      allergy_info: null,
      origin_info: null,
      options: null,
    });

    const user = userEvent.setup();
    render(<MenusPage />);

    await screen.findByText(/아직 등록된 메뉴가 없어요/);

    await user.type(
      screen.getByLabelText("또는 텍스트로 붙여넣기 (선택)"),
      "염소탕 15,000원\n염소탕(특) 20,000원"
    );
    await user.click(screen.getByRole("button", { name: "메뉴 추출하기" }));

    expect(draftMenusFromTextMock).toHaveBeenCalledWith(
      "test-token",
      "biz-1",
      "염소탕 15,000원\n염소탕(특) 20,000원"
    );

    const secondNameInput = await screen.findByDisplayValue("염소탕(특)");
    await user.click(screen.getByLabelText("염소탕(특) 포함"));
    expect(secondNameInput).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "선택한 메뉴 추가하기" }));

    expect(createMenuMock).toHaveBeenCalledTimes(1);
    expect(createMenuMock).toHaveBeenCalledWith("test-token", "biz-1", { name: "염소탕", price: "15000" });
    expect(await screen.findByText(/염소탕 — 15,000원/)).toBeInTheDocument();
  });

  it("추출 결과가 없으면 안내 문구를 보여준다", async () => {
    listMenusMock.mockResolvedValueOnce([]);
    draftMenusFromTextMock.mockResolvedValueOnce({ items: [] });

    const user = userEvent.setup();
    render(<MenusPage />);

    await screen.findByText(/아직 등록된 메뉴가 없어요/);

    await user.type(screen.getByLabelText("또는 텍스트로 붙여넣기 (선택)"), "리뷰 137개");
    await user.click(screen.getByRole("button", { name: "메뉴 추출하기" }));

    expect(await screen.findByText("추출할 수 있는 메뉴를 찾지 못했어요.")).toBeInTheDocument();
  });

  it("이미 등록된 메뉴를 대표로 설정/해제할 수 있다", async () => {
    listMenusMock.mockResolvedValueOnce([
      {
        id: "m1",
        business_id: "biz-1",
        name: "염소탕",
        description: null,
        price: "15000",
        image_url: null,
        is_signature: false,
        allergy_info: null,
        origin_info: null,
        options: null,
      },
    ]);
    updateMenuMock.mockResolvedValueOnce({
      id: "m1",
      business_id: "biz-1",
      name: "염소탕",
      description: null,
      price: "15000",
      image_url: null,
      is_signature: true,
      allergy_info: null,
      origin_info: null,
      options: null,
    });

    const user = userEvent.setup();
    render(<MenusPage />);

    await user.click(await screen.findByRole("button", { name: "대표로 설정" }));

    expect(updateMenuMock).toHaveBeenCalledWith("test-token", "biz-1", "m1", { is_signature: true });
    expect(await screen.findByText(/⭐ 염소탕/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "대표 해제" })).toBeInTheDocument();
  });

  it("메뉴명 입력 후 다른 곳을 클릭하면(포커스 이탈) 버튼을 안 눌러도 자동으로 설명 초안을 채운다", async () => {
    listMenusMock.mockResolvedValueOnce([]);
    draftMenuDescriptionMock.mockResolvedValueOnce({ description: "얼큰한 김치찌개예요." });

    const user = userEvent.setup();
    render(<MenusPage />);

    await screen.findByText(/아직 등록된 메뉴가 없어요/);

    await user.type(screen.getByLabelText(/메뉴명/), "김치찌개");
    await user.click(screen.getByLabelText(/가격/));

    expect(draftMenuDescriptionMock).toHaveBeenCalledWith("test-token", "biz-1", "김치찌개", false, "");
    expect(await screen.findByDisplayValue("얼큰한 김치찌개예요.")).toBeInTheDocument();
  });

  it("이미 등록된 메뉴의 설명/사진/원산지/알레르기 정보를 편집·저장할 수 있다", async () => {
    listMenusMock.mockResolvedValueOnce([
      {
        id: "m1",
        business_id: "biz-1",
        name: "염소탕(특)",
        description: null,
        price: "20000",
        image_url: null,
        is_signature: false,
        allergy_info: null,
        origin_info: null,
        options: null,
      },
    ]);
    draftMenuDescriptionMock.mockResolvedValueOnce({ description: "진하게 우려낸 특대 염소탕이에요." });
    updateMenuMock.mockResolvedValueOnce({
      id: "m1",
      business_id: "biz-1",
      name: "염소탕(특)",
      description: "진하게 우려낸 특대 염소탕이에요.",
      price: "20000",
      image_url: "https://example.com/goat-soup.jpg",
      is_signature: false,
      allergy_info: null,
      origin_info: "인천 강화 흑염소 사용",
      options: null,
    });

    const user = userEvent.setup();
    render(<MenusPage />);

    await user.click(await screen.findByRole("button", { name: "정보 편집" }));
    await user.type(screen.getByLabelText("재료/원산지"), "인천 강화 흑염소 사용");
    await user.click(screen.getAllByRole("button", { name: "AI가 초안 써줄게요" })[0]);

    expect(draftMenuDescriptionMock).toHaveBeenCalledWith(
      "test-token",
      "biz-1",
      "염소탕(특)",
      false,
      "인천 강화 흑염소 사용"
    );
    const textarea = await screen.findByDisplayValue("진하게 우려낸 특대 염소탕이에요.");
    await user.type(
      screen.getByLabelText("사진 URL"),
      "https://example.com/goat-soup.jpg"
    );

    await user.click(screen.getByRole("button", { name: "저장" }));

    expect(updateMenuMock).toHaveBeenCalledWith("test-token", "biz-1", "m1", {
      description: "진하게 우려낸 특대 염소탕이에요.",
      image_url: "https://example.com/goat-soup.jpg",
      origin_info: "인천 강화 흑염소 사용",
      allergy_info: "",
    });
    expect(await screen.findByText("진하게 우려낸 특대 염소탕이에요.")).toBeInTheDocument();
    expect(screen.getByText("재료/원산지: 인천 강화 흑염소 사용")).toBeInTheDocument();
    expect(textarea).not.toBeInTheDocument();
  });

  it("정보 편집 패널에서도 재료/원산지로 알레르기 정보를 채울 수 있다", async () => {
    listMenusMock.mockResolvedValueOnce([
      {
        id: "m1",
        business_id: "biz-1",
        name: "새우튀김",
        description: null,
        price: "8000",
        image_url: null,
        is_signature: false,
        allergy_info: null,
        origin_info: null,
        options: null,
      },
    ]);

    const user = userEvent.setup();
    render(<MenusPage />);

    await user.click(await screen.findByRole("button", { name: "정보 편집" }));
    await user.type(screen.getByLabelText("재료/원산지"), "새우와 밀가루를 사용한 튀김");
    await user.click(screen.getAllByRole("button", { name: "재료에서 채워줄게요" })[0]);

    expect(screen.getByLabelText("알레르기 정보")).toHaveValue("새우, 밀");
  });

  it("메뉴판 사진을 업로드해서 추출하면 후보 목록이 뜬다", async () => {
    listMenusMock.mockResolvedValueOnce([]);
    draftMenusFromImageMock.mockResolvedValueOnce({
      items: [
        { name: "염소탕", price: "15000" },
        { name: "염소탕(특)", price: "20000" },
      ],
    });

    const user = userEvent.setup();
    render(<MenusPage />);

    await screen.findByText(/아직 등록된 메뉴가 없어요/);

    const file = new File(["fake-bytes"], "menu.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("또는 파일에서 선택"), file);
    await user.click(screen.getByRole("button", { name: "사진에서 메뉴 추출하기" }));

    expect(draftMenusFromImageMock).toHaveBeenCalledWith("test-token", "biz-1", file);
    expect(await screen.findByDisplayValue("염소탕")).toBeInTheDocument();
    expect(screen.getByDisplayValue("염소탕(특)")).toBeInTheDocument();
  });

  it("메뉴판 사진을 붙여넣기(Ctrl+V)로도 선택할 수 있고, 다시 선택할 수도 있다", async () => {
    listMenusMock.mockResolvedValueOnce([]);

    const { container } = render(<MenusPage />);
    await screen.findByText(/아직 등록된 메뉴가 없어요/);

    const pasteAreas = container.querySelectorAll('div[tabindex="0"]');
    // 이 페이지엔 붙여넣기 영역이 메뉴판 이미지 하나뿐이다
    expect(pasteAreas.length).toBe(1);

    const file = new File(["fake-bytes"], "menu.png", { type: "image/png" });
    fireEvent.paste(pasteAreas[0], {
      clipboardData: { items: [{ type: "image/png", getAsFile: () => file }] },
    });

    expect(await screen.findByText("선택됨: menu.png")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "사진에서 메뉴 추출하기" })).toBeEnabled();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "선택 지우기" }));

    expect(screen.queryByText("선택됨: menu.png")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "사진에서 메뉴 추출하기" })).toBeDisabled();
  });
});
