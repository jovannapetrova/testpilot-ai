import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ForgotPassword from "./ForgotPassword";
import { renderWithRouter } from "../test/test-utils";
import { requestPasswordReset, resetPassword, verifyResetCode } from "../api/client";

vi.mock("../api/client", () => ({
  requestPasswordReset: vi.fn(),
  resetPassword: vi.fn(),
  verifyResetCode: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ForgotPassword", () => {
  it("requests a one-time verification code without exposing debug links", async () => {
    requestPasswordReset.mockResolvedValueOnce({
      delivery_configured: true,
      message: "If an account exists for that email, a verification code will be sent shortly.",
      resend_after_seconds: 0,
    });

    renderWithRouter(<ForgotPassword />);

    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: "person@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /send verification code/i }));

    await waitFor(() => {
      expect(requestPasswordReset).toHaveBeenCalledWith("person@example.com");
    });
    expect(await screen.findByLabelText(/verification code/i)).toBeInTheDocument();
    expect(screen.queryByText(/development reset link/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/open reset link/i)).not.toBeInTheDocument();
  });

  it("shows invalid-code feedback and keeps the user on the code step", async () => {
    requestPasswordReset.mockResolvedValueOnce({
      delivery_configured: true,
      message: "If an account exists for that email, a verification code will be sent shortly.",
      resend_after_seconds: 0,
    });
    verifyResetCode.mockRejectedValueOnce({ userMessage: "The verification code is invalid or expired." });

    renderWithRouter(<ForgotPassword />);

    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: "person@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /send verification code/i }));
    fireEvent.change(await screen.findByLabelText(/verification code/i), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: /verify code/i }));

    expect(await screen.findByText("The verification code is invalid or expired.")).toBeInTheDocument();
    expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument();
  });

  it("verifies a code and submits matching new passwords", async () => {
    requestPasswordReset.mockResolvedValueOnce({
      delivery_configured: true,
      message: "If an account exists for that email, a verification code will be sent shortly.",
      resend_after_seconds: 0,
    });
    verifyResetCode.mockResolvedValueOnce({ message: "Verification code accepted. Choose a new password." });
    resetPassword.mockResolvedValueOnce({ message: "Password reset successful. You can now sign in." });

    renderWithRouter(<ForgotPassword />);

    fireEvent.change(screen.getByLabelText(/^email$/i), { target: { value: "person@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /send verification code/i }));
    fireEvent.change(await screen.findByLabelText(/verification code/i), { target: { value: "654321" } });
    fireEvent.click(screen.getByRole("button", { name: /verify code/i }));

    fireEvent.change(await screen.findByLabelText(/^new password$/i), { target: { value: "new-strong-password" } });
    fireEvent.change(screen.getByLabelText(/confirm new password/i), { target: { value: "new-strong-password" } });
    fireEvent.click(screen.getByRole("button", { name: /reset password/i }));

    await waitFor(() => {
      expect(resetPassword).toHaveBeenCalledWith({
        email: "person@example.com",
        code: "654321",
        new_password: "new-strong-password",
        confirm_password: "new-strong-password",
      });
    });
    expect(await screen.findByText("Password reset successful.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to sign in/i })).toHaveAttribute("href", "/login");
  });
});
