import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

// vi.clearAllMocks() runs automatically via vitest.config.ts's
// test.clearMocks - see there rather than duplicating it here.
