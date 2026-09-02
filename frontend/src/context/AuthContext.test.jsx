import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import {
  getCurrentUser,
  loginUser,
  refreshSession,
  setAuthSession,
} from "../api/client";

const mocks = vi.hoisted(() => ({
  apiMock: {
    defaults: { headers: { common: {} } },
    interceptors: {
      request: { use: vi.fn(() => 1), eject: vi.fn() },
      response: { use: vi.fn(() => 1), eject: vi.fn() },
    },
  },
}));

vi.mock("../api/client", () => ({
  default: mocks.apiMock,
  getCurrentUser: vi.fn(),
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  refreshSession: vi.fn(),
  registerUser: vi.fn(),
  setAuthSession: vi.fn(),
}));

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="auth-state">{auth.loading ? "loading" : auth.isAuthenticated ? "authenticated" : "anonymous"}</span>
      <span data-testid="notice">{auth.authNotice}</span>
      <button
        type="button"
        onClick={() => auth.login({ email: "person@example.com", password: "strong-password", remember_me: false })}
      >
        login session
      </button>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

describe("AuthContext", () => {
  it("restores a stored session by validating it with the API", async () => {
    localStorage.setItem("testpilot-session", JSON.stringify({ access_token: "token", refresh_token: "refresh" }));
    getCurrentUser.mockResolvedValueOnce({ user: { email: "person@example.com" } });

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId("auth-state")).toHaveTextContent("authenticated"));
    expect(setAuthSession).toHaveBeenCalled();
  });

  it("clears expired sessions when refresh fails", async () => {
    localStorage.setItem("testpilot-session", JSON.stringify({ access_token: "expired", refresh_token: "expired-refresh" }));
    getCurrentUser.mockRejectedValueOnce(new Error("expired"));
    refreshSession.mockRejectedValueOnce(new Error("expired"));

    render(<AuthProvider><Probe /></AuthProvider>);

    await waitFor(() => expect(screen.getByTestId("auth-state")).toHaveTextContent("anonymous"));
    expect(localStorage.getItem("testpilot-session")).toBeNull();
    expect(screen.getByTestId("notice")).toHaveTextContent("Your session has expired. Please sign in again.");
  });

  it("keeps remember-me false sessions in sessionStorage", async () => {
    getCurrentUser.mockResolvedValueOnce({ user: { email: "person@example.com" } });
    loginUser.mockResolvedValueOnce({
      access_token: "token",
      refresh_token: "refresh",
      user: { email: "person@example.com" },
    });

    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("auth-state")).toHaveTextContent("anonymous"));

    await act(async () => {
      screen.getByRole("button", { name: /login session/i }).click();
    });

    await waitFor(() => {
      expect(localStorage.getItem("testpilot-session")).toBeNull();
      expect(sessionStorage.getItem("testpilot-session-memory")).toContain("token");
    });
  });
});
