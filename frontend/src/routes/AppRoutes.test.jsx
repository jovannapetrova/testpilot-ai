import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AppRoutes from "./AppRoutes";
import { renderWithRouter } from "../test/test-utils";
import { useAuth } from "../context/AuthContext";

vi.mock("../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

describe("AppRoutes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects unauthenticated protected routes to login", async () => {
    useAuth.mockReturnValue({
      isAuthenticated: false,
      loading: false,
      login: vi.fn(),
      authNotice: "",
      clearAuthNotice: vi.fn(),
    });

    renderWithRouter(<AppRoutes />, ["/dashboard"]);

    expect(await screen.findByText(/welcome back/i)).toBeInTheDocument();
  });
});
