import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// P1-4 (REORG_DECISIONS.md) - request()의 마지막 안전장치(AbortController
// 타임아웃)만 독립적으로 검증한다. 이건 컴포넌트가 아니라 순수 fetch 래퍼라
// 다른 테스트처럼 render()가 필요 없다.
import { api, ApiError } from "@/lib/api";

describe("lib/api.ts - request() 타임아웃 안전장치", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("백엔드가 25초 넘게 응답이 없으면 fetch를 중단하고 친절한 ApiError를 던진다", async () => {
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          const err = new DOMException("The operation was aborted.", "AbortError");
          reject(err);
        });
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const promise = api.myBusinesses("test-token");
    // toRejects 쪽 assertion을 먼저 걸어두고 타이머를 돌려야, 타이머가
    // reject를 만들어내는 시점과 assertion 등록 순서가 안 꼬인다.
    const assertion = expect(promise).rejects.toBeInstanceOf(ApiError);

    await vi.advanceTimersByTimeAsync(25_000);

    await assertion;
    await expect(promise).rejects.toMatchObject({
      message: "요청 시간이 너무 오래 걸려요. 잠시 후 다시 시도해 주세요.",
    });
  });

  it("정상 응답은 타임아웃 없이 그대로 반환된다", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify([{ id: "biz-1" }]), { status: 200, headers: { "Content-Type": "application/json" } })
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.myBusinesses("test-token");
    expect(result).toEqual([{ id: "biz-1" }]);
  });
});
