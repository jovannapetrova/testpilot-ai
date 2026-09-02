import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Register from "./Register";
import { renderWithRouter } from "../test/test-utils";
import { useAuth } from "../context/AuthContext";

vi.mock("../context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const register = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({ register });
});

describe("Register", () => {
  it("creates an account with validated form input", async () => {
    register.mockResolvedValueOnce({ access_token: "token" });
    renderWithRouter(<Register />);

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Jane Peterson" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "strong-password" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => {
      expect(register).toHaveBeenCalledWith({
        full_name: "Jane Peterson",
        email: "jane@example.com",
        password: "strong-password",
      });
    });
  });

  it("shows duplicate registration feedback from the API", async () => {
    register.mockRejectedValueOnce({ userMessage: "An account with this email already exists." });
    renderWithRouter(<Register />);

    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Jane Peterson" } });
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "strong-password" } });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(await screen.findByText("An account with this email already exists.")).toBeInTheDocument();
  });
});
