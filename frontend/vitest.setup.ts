import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

// vi.clearAllMocks() runs automatically via vitest.config.ts's
// test.clearMocks - see there rather than duplicating it here.

// jsdom doesn't implement these - needed by any component that shows an
// <img> preview of a locally-selected File (e.g. businesses/[id]/profile).
if (!URL.createObjectURL) URL.createObjectURL = vi.fn(() => "blob:mock-url");
if (!URL.revokeObjectURL) URL.revokeObjectURL = vi.fn();
