import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  getBusinessMock,
  getProfileMock,
  listMenusMock,
  listCouponsMock,
  chatMock,
  createReservationMock,
  submitChatFeedbackMock,
} = vi.hoisted(() => ({
  getBusinessMock: vi.fn(),
  getProfileMock: vi.fn(),
  listMenusMock: vi.fn(),
  listCouponsMock: vi.fn(),
  chatMock: vi.fn(),
  createReservationMock: vi.fn(),
  submitChatFeedbackMock: vi.fn(),
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
      createReservation: createReservationMock,
      submitChatFeedback: submitChatFeedbackMock,
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
      reservation_draft: null,
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    expect(await screen.findByText("영종 식당")).toBeInTheDocument();
    expect(screen.queryByText(/Chef AI에게 물어보세요/)).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "전송" })).toHaveLength(1);

    const chatInput = screen.getByPlaceholderText("예: 내일 저녁 7시에 3명 예약하고 싶어요");
    await user.type(chatInput, "매운 거 추천해줘");
    const chatForm = chatInput.closest("form");
    if (!chatForm) throw new Error("AI chat form not found");
    await user.click(within(chatForm).getByRole("button", { name: "전송" }));

    expect(await screen.findByText("대표 메뉴인 짜장면을 추천드려요!")).toBeInTheDocument();
    // 위젯이 처음부터 들고 있던 인사말(greeting)이 첫 메시지 시점의 history다.
    expect(chatMock).toHaveBeenCalledWith("biz-1", "매운 거 추천해줘", [
      { role: "ai", text: expect.stringContaining("영업시간") },
    ]);
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
      reservation_draft: null,
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    expect(await screen.findByText("영종 식당")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("예: 내일 저녁 7시에 3명 예약하고 싶어요"), "강아지 데려가도 되나요?");
    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByText("네, 실외석에서는 반려동물과 함께하실 수 있어요.")).toBeInTheDocument();
    expect(chatMock).toHaveBeenCalledWith("biz-1", "강아지 데려가도 되나요?", [
      { role: "ai", text: expect.stringContaining("영업시간") },
    ]);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByText("예약 내용을 확인해주세요")).not.toBeInTheDocument();
  });
});

describe("BusinessDetailPage (smoke) - P1-5 채팅 피드백(👍/👎)", () => {
  it("interaction_id가 있는 답변에는 피드백 버튼이 뜨고, 누르면 submitChatFeedback을 호출한다", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    getProfileMock.mockResolvedValueOnce(null);
    listMenusMock.mockResolvedValueOnce([]);
    listCouponsMock.mockResolvedValueOnce([]);
    chatMock.mockResolvedValueOnce({
      agent_type: "customer",
      reply: "네, 오늘 영업합니다!",
      menu_images: [],
      reservation_draft: null,
      interaction_id: "int-1",
    });
    submitChatFeedbackMock.mockResolvedValueOnce({ id: "int-1", feedback: "UP" });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    await screen.findByText("영종 식당");
    await user.type(screen.getByPlaceholderText("예: 내일 저녁 7시에 3명 예약하고 싶어요"), "오늘 영업하나요?");
    await user.click(screen.getByRole("button", { name: "전송" }));

    await screen.findByText("네, 오늘 영업합니다!");
    await user.click(screen.getByRole("button", { name: "도움이 됐어요" }));

    expect(submitChatFeedbackMock).toHaveBeenCalledWith("int-1", "UP");
  });

  it("interaction_id가 없는 답변(오류 메시지 등)에는 피드백 버튼이 안 뜬다", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    getProfileMock.mockResolvedValueOnce(null);
    listMenusMock.mockResolvedValueOnce([]);
    listCouponsMock.mockResolvedValueOnce([]);
    chatMock.mockResolvedValueOnce({
      agent_type: "customer",
      reply: "네, 오늘 영업합니다!",
      menu_images: [],
      reservation_draft: null,
      interaction_id: null,
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    await screen.findByText("영종 식당");
    await user.type(screen.getByPlaceholderText("예: 내일 저녁 7시에 3명 예약하고 싶어요"), "오늘 영업하나요?");
    await user.click(screen.getByRole("button", { name: "전송" }));

    await screen.findByText("네, 오늘 영업합니다!");
    expect(screen.queryByRole("button", { name: "도움이 됐어요" })).not.toBeInTheDocument();
  });
});

describe("BusinessDetailPage (smoke) - P1-6 대화형 예약 (AI 확인 카드)", () => {
  const noProfileCoupons = () => {
    getProfileMock.mockResolvedValueOnce(null);
    listCouponsMock.mockResolvedValueOnce([]);
    listMenusMock.mockResolvedValueOnce([]);
  };

  it("예약 의도가 없는 일반 대화에서는 확인 카드가 뜨지 않는다", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    noProfileCoupons();
    chatMock.mockResolvedValueOnce({
      agent_type: "customer",
      reply: "네, 오늘도 영업합니다!",
      menu_images: [],
      reservation_draft: null,
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    await screen.findByText("영종 식당");
    await user.type(screen.getByPlaceholderText("예: 내일 저녁 7시에 3명 예약하고 싶어요"), "오늘 영업하나요?");
    await user.click(screen.getByRole("button", { name: "전송" }));

    await screen.findByText("네, 오늘도 영업합니다!");
    expect(screen.queryByText("예약 내용을 확인해주세요")).not.toBeInTheDocument();
  });

  it("일부 정보만 모였을 때는 확인 카드는 뜨지만 [예약 확정]은 비활성화된다", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    noProfileCoupons();
    chatMock.mockResolvedValueOnce({
      agent_type: "customer",
      reply: "성함과 연락처를 알려주시겠어요?",
      menu_images: [],
      reservation_draft: {
        customer_name: null,
        customer_phone: null,
        date: "2026-08-26",
        time: "19:00",
        party_size: 3,
        notes: null,
      },
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    await screen.findByText("영종 식당");
    await user.type(
      screen.getByPlaceholderText("예: 내일 저녁 7시에 3명 예약하고 싶어요"),
      "내일 저녁 7시에 3명 예약하고 싶어요"
    );
    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByText("예약 내용을 확인해주세요")).toBeInTheDocument();
    expect(screen.getAllByText("확인 필요").length).toBe(2); // 이름, 연락처
    expect(screen.getByText("3명")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "예약 확정" })).toBeDisabled();
    expect(createReservationMock).not.toHaveBeenCalled();
  });

  it("모든 정보가 채워지면 [예약 확정]이 활성화되고, 클릭하면 기존 createReservation을 호출한다", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    noProfileCoupons();
    chatMock.mockResolvedValueOnce({
      agent_type: "customer",
      reply: "예약 요청 내용을 접수했어요. 사장님이 확인 후 확정해드립니다.",
      menu_images: [],
      reservation_draft: {
        customer_name: "김손님",
        customer_phone: "010-1111-2222",
        date: "2026-08-26",
        time: "19:00",
        party_size: 4,
        notes: "창가 자리 요청",
      },
    });
    createReservationMock.mockResolvedValueOnce({
      id: "r1",
      business_id: "biz-1",
      customer_name: "김손님",
      customer_phone: "010-1111-2222",
      reservation_time: "2026-08-26T19:00:00.000Z",
      party_size: 4,
      notes: "창가 자리 요청",
      status: "REQUESTED",
      created_at: "2026-08-25T00:00:00Z",
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    await screen.findByText("영종 식당");
    await user.type(
      screen.getByPlaceholderText("예: 내일 저녁 7시에 3명 예약하고 싶어요"),
      "내일 저녁 7시에 4명, 김손님, 010-1111-2222예요"
    );
    await user.click(screen.getByRole("button", { name: "전송" }));

    const confirmButton = await screen.findByRole("button", { name: "예약 확정" });
    expect(confirmButton).toBeEnabled();
    expect(createReservationMock).not.toHaveBeenCalled(); // 확정 전에는 절대 생성되지 않는다

    await user.click(confirmButton);

    expect(createReservationMock).toHaveBeenCalledWith("biz-1", {
      customer_name: "김손님",
      customer_phone: "010-1111-2222",
      reservation_time: new Date("2026-08-26T19:00").toISOString(),
      party_size: 4,
      notes: "창가 자리 요청",
    });
    expect(await screen.findByText("예약 요청이 접수되었어요. 업체에서 확인 후 확정 연락을 드려요.")).toBeInTheDocument();
    expect(screen.queryByText("예약 내용을 확인해주세요")).not.toBeInTheDocument();
  });

  it("정정 발화 이후 응답은 이전 draft를 덮어써서 최신 값을 보여준다", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    noProfileCoupons();
    chatMock
      .mockResolvedValueOnce({
        agent_type: "customer",
        reply: "3명으로 준비할게요. 성함과 연락처를 알려주세요.",
        menu_images: [],
        reservation_draft: {
          customer_name: null,
          customer_phone: null,
          date: "2026-08-26",
          time: "19:00",
          party_size: 3,
          notes: null,
        },
      })
      .mockResolvedValueOnce({
        agent_type: "customer",
        reply: "4명으로 정정했습니다.",
        menu_images: [],
        reservation_draft: {
          customer_name: null,
          customer_phone: null,
          date: "2026-08-26",
          time: "19:00",
          party_size: 4,
          notes: null,
        },
      });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    await screen.findByText("영종 식당");
    const input = screen.getByPlaceholderText("예: 내일 저녁 7시에 3명 예약하고 싶어요");
    await user.type(input, "내일 저녁 7시에 3명 예약할게요");
    await user.click(screen.getByRole("button", { name: "전송" }));
    await screen.findByText("3명");

    await user.type(input, "아 4명이요");
    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByText("4명")).toBeInTheDocument();
    expect(screen.queryByText("3명")).not.toBeInTheDocument();
    expect(chatMock).toHaveBeenLastCalledWith("biz-1", "아 4명이요", [
      { role: "ai", text: expect.stringContaining("영업시간") },
      { role: "user", text: "내일 저녁 7시에 3명 예약할게요" },
      { role: "ai", text: "3명으로 준비할게요. 성함과 연락처를 알려주세요." },
    ]);
  });

  it("P0-2 - 수동 예약 폼은 기본적으로 접혀있고 AI 대화가 먼저 보인다", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    noProfileCoupons();

    render(<BusinessDetailPage />);

    await screen.findByText("영종 식당");
    expect(screen.getByRole("button", { name: "AI 대화 대신 양식으로 직접 예약할게요" })).toBeInTheDocument();
    expect(screen.queryByLabelText("이름 *")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "예약 요청하기" })).not.toBeInTheDocument();
  });

  it("기존 수동 예약 폼은 그대로 동작한다", async () => {
    getBusinessMock.mockResolvedValueOnce(business);
    noProfileCoupons();
    createReservationMock.mockResolvedValueOnce({
      id: "r2",
      business_id: "biz-1",
      customer_name: "박손님",
      customer_phone: "010-2222-3333",
      reservation_time: "2026-08-27T18:00:00.000Z",
      party_size: 2,
      notes: null,
      status: "REQUESTED",
      created_at: "2026-08-25T00:00:00Z",
    });

    const user = userEvent.setup();
    render(<BusinessDetailPage />);

    await screen.findByText("영종 식당");
    // P0-2 - 수동 폼은 기본적으로 접혀있고, 링크를 눌러야 펼쳐진다.
    await user.click(screen.getByRole("button", { name: "AI 대화 대신 양식으로 직접 예약할게요" }));
    await user.type(screen.getByLabelText("이름 *"), "박손님");
    await user.type(screen.getByLabelText("연락처 *"), "010-2222-3333");
    await user.type(screen.getByLabelText("날짜 및 시간 *"), "2026-08-27T18:00");
    await user.click(screen.getByRole("button", { name: "예약 요청하기" }));

    expect(createReservationMock).toHaveBeenCalledWith("biz-1", {
      customer_name: "박손님",
      customer_phone: "010-2222-3333",
      reservation_time: new Date("2026-08-27T18:00").toISOString(),
      party_size: 2,
      notes: undefined,
    });
    expect(
      await screen.findByText("예약 요청이 접수되었어요. 업체에서 확인 후 확정 연락을 드려요.")
    ).toBeInTheDocument();
  });
});
