import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Login from "./Login";
import { renderWithRouter } from "../test/test-utils";
import { useAuth } from "../context/AuthContext";

vi.mock("../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const login = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({
    login,
    authNotice: "",
    clearAuthNotice: vi.fn(),
  });
});

describe("Login", () => {
  it("submits credentials with remember-me enabled by default", async () => {
    login.mockResolvedValueOnce({ access_token: "token" });
    renderWithRouter(<Login />);

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "person@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "strong-password" } });
    fireEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({
        email: "person@example.com",
        password: "strong-password",
        remember_me: true,
      });
    });
  });

  it("shows a friendly wrong-password message", async () => {
    login.mockRejectedValueOnce({ userMessage: "Incorrect email or password." });
    renderWithRouter(<Login />);

    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "person@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "bad-password" } });
    fireEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(await screen.findByText("Incorrect email or password.")).toBeInTheDocument();
  });

  it("does not expose magic-link sign-in controls", () => {
    renderWithRouter(<Login />);

    expect(screen.queryByRole("button", { name: /email me a sign-in link/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /forgot password/i })).toHaveAttribute("href", "/forgot-password");
  });
});
