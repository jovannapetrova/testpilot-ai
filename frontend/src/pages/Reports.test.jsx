import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Reports from "./Reports";
import { renderWithRouter } from "../test/test-utils";
import { deleteReport, getReports } from "../api/client";

vi.mock("../api/client", () => ({
  clearReports: vi.fn(),
  compareReports: vi.fn(),
  deleteReport: vi.fn(),
  downloadReportFile: vi.fn(),
  getReport: vi.fn(),
  getReports: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
});

describe("Reports", () => {
  it("shows an empty state when there are no persisted reports", async () => {
    getReports.mockResolvedValueOnce({ reports: [] });

    renderWithRouter(<Reports />);

    await waitFor(() => expect(getReports).toHaveBeenCalled());
    expect(await screen.findByText("No reports generated yet")).toBeInTheDocument();
  });

  it("confirms and deletes a selected report", async () => {
    getReports
      .mockResolvedValueOnce({
        reports: [{ project_id: "one", project_name: "Billing API", created_at: new Date().toISOString(), overall_score: 90, quality_score: 91, security_score: 92, test_score: 88 }],
      })
      .mockResolvedValueOnce({ reports: [] });
    deleteReport.mockResolvedValueOnce({ success: true });

    renderWithRouter(<Reports />);

    expect(await screen.findAllByText("Billing API")).not.toHaveLength(0);
    expect(screen.getByText("Average Overall Score")).toBeInTheDocument();
    expect(screen.getByText("Average Security Score")).toBeInTheDocument();
    expect(screen.getByText("Average Testing Score")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("Delete report"));
    const deleteButtons = screen.getAllByRole("button", { name: /delete report/i });
    fireEvent.click(deleteButtons[deleteButtons.length - 1]);

    await waitFor(() => expect(deleteReport).toHaveBeenCalledWith("one"));
  });
});
