import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { routerMock, getOwnerProfileMock, updateProfileMock, analyzeExpansionMock, draftProfileFromImageMock } =
  vi.hoisted(() => ({
    routerMock: { push: vi.fn() },
    getOwnerProfileMock: vi.fn(),
    updateProfileMock: vi.fn(),
    analyzeExpansionMock: vi.fn(),
    draftProfileFromImageMock: vi.fn(),
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
      getOwnerProfile: getOwnerProfileMock,
      updateProfile: updateProfileMock,
      analyzeExpansion: analyzeExpansionMock,
      draftProfileFromImage: draftProfileFromImageMock,
    },
  };
});

import BusinessProfilePage from "@/app/businesses/[id]/profile/page";

function makeOwnerProfile(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "profile-1",
    business_id: "biz-1",
    description: null,
    brand_tone: null,
    opening_hours: null,
    holiday: null,
    parking: null,
    pet_policy: null,
    reservation_policy: null,
    takeout_policy: null,
    payment_methods: null,
    faq: null,
    naver_place_url: null,
    naver_map_url: null,
    monthly_visitor_estimate: null,
    ...overrides,
  };
}

describe("BusinessProfilePage - P0-3 온보딩 완료 체감 순간", () => {
  it("저장 전에는 완료 카드가 안 뜬다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());

    render(<BusinessProfilePage />);

    expect(await screen.findByText("Step 3 / 3 · AI 정보")).toBeInTheDocument();
    expect(screen.queryByText("🎉 우리 가게 AI가 준비됐어요!")).not.toBeInTheDocument();
  });

  it("저장하면 완료 카드가 뜨고, AI 테스트와 Home 공개 링크가 둘 다 보인다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());
    updateProfileMock.mockResolvedValueOnce(makeOwnerProfile({ description: "설명" }));
    analyzeExpansionMock.mockResolvedValueOnce([]);

    const user = userEvent.setup();
    render(<BusinessProfilePage />);

    await screen.findByText("Step 3 / 3 · AI 정보");
    await user.type(screen.getByLabelText("가게 소개"), "설명");
    await user.click(screen.getByRole("button", { name: "저장하기" }));

    expect(await screen.findByText("🎉 우리 가게 AI가 준비됐어요!")).toBeInTheDocument();

    const testLink = screen.getByRole("link", { name: "AI 테스트해보기 →" });
    expect(testLink).toHaveAttribute("href", "/businesses/biz-1");

    const homeLink = screen.getByRole("link", { name: "Home에서 공개하기 →" });
    expect(homeLink).toHaveAttribute("href", "/dashboard");
  });
});

describe("BusinessProfilePage - 네이버 화면 캡쳐 업로드로 정보 채우기", () => {
  it("사진을 업로드하고 추출하면, 돌아온 항목만 폼에 채워진다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());
    draftProfileFromImageMock.mockResolvedValueOnce({
      description: "영종식당은 바지락 칼국수를 대표 메뉴로 하는 식당입니다.",
      opening_hours: "매일 10:00 - 21:00",
      holiday: "매주 월요일",
      parking: null,
      pet_policy: null,
      reservation_policy: "전화 또는 앱으로 예약",
      takeout_policy: null,
      payment_methods: "카드, 현금",
    });

    const user = userEvent.setup();
    render(<BusinessProfilePage />);

    await screen.findByText("Step 3 / 3 · AI 정보");

    const file = new File(["fake-bytes"], "naver.png", { type: "image/png" });
    const fileInput = screen.getByLabelText("또는 파일에서 선택");
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: "사진에서 정보 추출하기" }));

    expect(draftProfileFromImageMock).toHaveBeenCalledWith("test-token", "biz-1", file);
    expect(await screen.findByDisplayValue("영종식당은 바지락 칼국수를 대표 메뉴로 하는 식당입니다.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("매일 10:00 - 21:00")).toBeInTheDocument();
    expect(screen.getByDisplayValue("매주 월요일")).toBeInTheDocument();
    expect(screen.getByDisplayValue("전화 또는 앱으로 예약")).toBeInTheDocument();
    expect(screen.getByDisplayValue("카드, 현금")).toBeInTheDocument();
    // parking/pet_policy came back null - untouched, still empty
    expect(screen.getByLabelText("주차")).toHaveValue("");
    expect(
      screen.getByText("5개 항목을 채웠어요 — 아래에서 확인하고 저장하세요.")
    ).toBeInTheDocument();
  });

  it("이미지에서 채울 항목을 하나도 못 찾으면 그렇게 안내한다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());
    draftProfileFromImageMock.mockResolvedValueOnce({
      description: null,
      opening_hours: null,
      holiday: null,
      parking: null,
      pet_policy: null,
      reservation_policy: null,
      takeout_policy: null,
      payment_methods: null,
    });

    const user = userEvent.setup();
    render(<BusinessProfilePage />);

    await screen.findByText("Step 3 / 3 · AI 정보");
    const file = new File(["fake-bytes"], "blurry.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("또는 파일에서 선택"), file);
    await user.click(screen.getByRole("button", { name: "사진에서 정보 추출하기" }));

    expect(await screen.findByText("이미지에서 채울 수 있는 항목을 찾지 못했어요.")).toBeInTheDocument();
  });

  it("파일을 고르기 전엔 추출 버튼이 비활성화된다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());

    render(<BusinessProfilePage />);

    await screen.findByText("Step 3 / 3 · AI 정보");
    expect(screen.getByRole("button", { name: "사진에서 정보 추출하기" })).toBeDisabled();
  });

  it("클립보드에 있는 이미지를 붙여넣기(Ctrl+V)로도 선택할 수 있다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());

    const { container } = render(<BusinessProfilePage />);
    await screen.findByText("Step 3 / 3 · AI 정보");

    const file = new File(["fake-bytes"], "clipboard.png", { type: "image/png" });
    const pasteArea = container.querySelector('div[tabindex="0"]');
    expect(pasteArea).not.toBeNull();

    fireEvent.paste(pasteArea as Element, {
      clipboardData: { items: [{ type: "image/png", getAsFile: () => file }] },
    });

    expect(await screen.findByText("선택됨: clipboard.png")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "사진에서 정보 추출하기" })).toBeEnabled();
  });

  it("'선택 지우기'를 누르면 다시 붙여넣기 안내로 돌아가고 추출 버튼이 비활성화된다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());

    const { container } = render(<BusinessProfilePage />);
    await screen.findByText("Step 3 / 3 · AI 정보");

    const file = new File(["fake-bytes"], "clipboard.png", { type: "image/png" });
    const pasteArea = container.querySelector('div[tabindex="0"]');
    fireEvent.paste(pasteArea as Element, {
      clipboardData: { items: [{ type: "image/png", getAsFile: () => file }] },
    });
    await screen.findByText("선택됨: clipboard.png");

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "선택 지우기" }));

    expect(screen.queryByText("선택됨: clipboard.png")).not.toBeInTheDocument();
    expect(screen.getByText("여기를 클릭한 뒤 Ctrl+V로 캡쳐한 이미지를 붙여넣으세요")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "사진에서 정보 추출하기" })).toBeDisabled();
  });

  it("이미지를 붙여넣은 뒤 다른 이미지를 다시 붙여넣으면 새 이미지로 바뀐다", async () => {
    getOwnerProfileMock.mockResolvedValueOnce(makeOwnerProfile());

    const { container } = render(<BusinessProfilePage />);
    await screen.findByText("Step 3 / 3 · AI 정보");
    const pasteArea = container.querySelector('div[tabindex="0"]') as Element;

    fireEvent.paste(pasteArea, {
      clipboardData: {
        items: [{ type: "image/png", getAsFile: () => new File(["a"], "first.png", { type: "image/png" }) }],
      },
    });
    await screen.findByText("선택됨: first.png");

    fireEvent.paste(pasteArea, {
      clipboardData: {
        items: [{ type: "image/png", getAsFile: () => new File(["b"], "second.png", { type: "image/png" }) }],
      },
    });

    expect(await screen.findByText("선택됨: second.png")).toBeInTheDocument();
    expect(screen.queryByText("선택됨: first.png")).not.toBeInTheDocument();
  });
});
