import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "./Dashboard";
import { renderWithRouter } from "../test/test-utils";
import { getDashboardSummary, getReport } from "../api/client";

vi.mock("../api/client", () => ({
  getDashboardSummary: vi.fn(),
  getReport: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Dashboard", () => {
  it("uses self-explanatory score labels and idle agent state for completed history", async () => {
    getDashboardSummary.mockResolvedValue({
      summary: {
        total_reports: 1,
        total_completed_reports: 1,
        avg_overall: 82,
        avg_quality: 80,
        avg_security: 90,
        avg_testing: 76,
        security_findings: 2,
        generated_tests: 4,
        running_projects: 0,
        latest_reports: [
          {
            project_id: "report-1",
            project_name: "Billing API",
            overall_score: 82,
            quality_score: 80,
            security_score: 90,
            test_score: 76,
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
    });
    getReport.mockResolvedValue({
      report: {
        agent_logs: [
          { name: "Project Detector Agent", status: "completed", message: "Completed successfully" },
          { name: "Report Agent", status: "completed", message: "Completed successfully" },
        ],
      },
    });

    renderWithRouter(<Dashboard />);

    expect(await screen.findAllByText("Average Overall Score")).not.toHaveLength(0);
    expect(screen.getByText("Generated, not executed evidence")).toBeInTheDocument();
    await waitFor(() => expect(getReport).toHaveBeenCalledWith("report-1"));
    expect(screen.getByText("System state: Ready")).toBeInTheDocument();
    expect(screen.getByText("Last run: 2/2 agents completed.")).toBeInTheDocument();
  });
});
