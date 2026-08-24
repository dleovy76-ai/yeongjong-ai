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
  });

  it("redirects to /login when the session has no token (인증 만료 상태)", () => {
    authStateRef.current = { token: null, loading: false };
    render(<ExpansionPage />);

    expect(pushMock).toHaveBeenCalledWith("/login");
  });
});
