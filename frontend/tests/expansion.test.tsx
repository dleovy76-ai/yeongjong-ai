import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { routerMock, authStateRef, listExpansionMock, listIncomingMock } = vi.hoisted(() => ({
  routerMock: { push: vi.fn() },
  authStateRef: { current: { token: "test-token" as string | null, loading: false } },
  listExpansionMock: vi.fn(),
  listIncomingMock: vi.fn(),
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
    api: {
      ...actual.api,
      listExpansion: listExpansionMock,
      listIncomingExpansionInvites: listIncomingMock,
    },
  };
});

import ExpansionPage from "@/app/businesses/[id]/expansion/page";

describe("ExpansionPage (smoke) - Expansion AI", () => {
  it("renders the recommended-partners heading and a suggestion once loaded", async () => {
    authStateRef.current = { token: "test-token", loading: false };
    listExpansionMock.mockResolvedValueOnce([
      {
        business_b_id: "biz-2",
        name_ko: "데모카페C",
        category: "CAFE",
        score: 90,
        reason: "근처에 있고 손님층이 겹쳐요",
        status: "SUGGESTED",
        invite_message: null,
        effect_estimate: null,
      },
    ]);
    listIncomingMock.mockResolvedValueOnce([]);

    render(<ExpansionPage />);

    expect(screen.getByRole("heading", { name: "연관업체 추천" })).toBeInTheDocument();
    expect(await screen.findByText("데모카페C")).toBeInTheDocument();

    // P1-4 - "적합도 90"처럼 점수를 헤더에 정량 지표로 내세우지 않고,
    // AI 추천 이유를 먼저 보여준 뒤 점수는 재현 불가능하다는 캡션과 함께
    // 보조 정보로만 표시한다.
    expect(screen.getByText("AI 추천 이유")).toBeInTheDocument();
    expect(screen.getByText("근처에 있고 손님층이 겹쳐요")).toBeInTheDocument();
    expect(
      screen.getByText("참고 점수 90점 · AI가 그때그때 판단한 값이라 다시 분석하면 달라질 수 있어요.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/적합도 90/)).not.toBeInTheDocument();
  });

  it("redirects to /login when the session has no token (인증 만료 상태)", () => {
    authStateRef.current = { token: null, loading: false };
    render(<ExpansionPage />);

    expect(pushMock).toHaveBeenCalledWith("/login");
  });

  it("추천 결과가 없을 때 분석 후 어떤 일이 일어나는지 설명한다", async () => {
    authStateRef.current = { token: "test-token", loading: false };
    listExpansionMock.mockResolvedValueOnce([]);
    listIncomingMock.mockResolvedValueOnce([]);

    render(<ExpansionPage />);

    expect(
      await screen.findByText("아직 추천 결과가 없어요. 위 버튼으로 분석을 시작해 보세요.")
    ).toBeInTheDocument();
    expect(screen.getByText(/상대가 수락하면 서로의 손님 AI 대화에서 자연스럽게 서로를 추천해줘요/)).toBeInTheDocument();
  });
});
