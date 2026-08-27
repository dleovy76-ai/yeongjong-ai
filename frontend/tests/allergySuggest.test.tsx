import { describe, expect, it } from "vitest";
import { suggestAllergyInfo } from "@/lib/allergySuggest";

describe("suggestAllergyInfo", () => {
  it("matches a single known allergen keyword", () => {
    expect(suggestAllergyInfo("인천 앞바다에서 직접 잡은 새우 사용")).toBe("새우");
  });

  it("matches multiple different allergens without duplicates", () => {
    // 매칭 순서는 입력 텍스트 순서가 아니라 내부 키워드 표 순서를 따른다
    expect(suggestAllergyInfo("새우와 밀가루, 계란을 사용한 튀김")).toBe("새우, 난류(계란), 밀");
  });

  it("dedupes when several keywords map to the same label", () => {
    expect(suggestAllergyInfo("우유와 치즈, 생크림이 들어간 소스")).toBe("우유");
  });

  it("returns an empty string when nothing matches", () => {
    expect(suggestAllergyInfo("인천 앞바다에서 직접 잡은 백합 사용")).toBe("");
  });

  it("returns an empty string for empty input", () => {
    expect(suggestAllergyInfo("")).toBe("");
  });
});
