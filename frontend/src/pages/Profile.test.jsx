import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Profile from "./Profile";
import { renderWithRouter } from "../test/test-utils";
import { updateCurrentUser } from "../api/client";

const mocks = vi.hoisted(() => ({
  setSession: vi.fn(),
}));

vi.mock("../api/client", () => ({
  changePassword: vi.fn(),
  updateCurrentUser: vi.fn(),
}));

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      full_name: "Ada Lovelace",
      email: "ada@example.com",
      created_at: "2026-01-01T00:00:00Z",
      last_login_at: null,
    },
    session: { remember_me: true },
    setSession: mocks.setSession,
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.setSession.mockClear();
});

describe("Profile", () => {
  it("keeps profile editing focused on supported user-facing fields", async () => {
    updateCurrentUser.mockResolvedValueOnce({
      user: { full_name: "Ada Byron", email: "ada@example.com" },
    });

    renderWithRouter(<Profile />);

    expect(screen.queryByLabelText(/avatar url/i)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Ada Byron" } });
    fireEvent.click(screen.getByRole("button", { name: /save profile/i }));

    await waitFor(() => {
      expect(updateCurrentUser).toHaveBeenCalledWith({ full_name: "Ada Byron" });
    });
  });
});
