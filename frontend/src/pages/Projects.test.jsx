import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Projects from "./Projects";
import { renderWithRouter } from "../test/test-utils";
import { getProjects, getReport } from "../api/client";

vi.mock("../api/client", () => ({
  getProjects: vi.fn(),
  getReport: vi.fn(),
  uploadProjectZip: vi.fn(),
  analyzeProject: vi.fn(),
  analyzeGithubRepository: vi.fn(),
  getAnalysisProgress: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Projects", () => {
  it("filters project archive by search text", async () => {
    getProjects.mockResolvedValueOnce({
      projects: [
        { project_id: "one", project_name: "Billing API", language: "Python", status: "completed", source_type: "github", overall_score: 91 },
        { project_id: "two", project_name: "Website", language: "JavaScript", status: "completed", source_type: "upload", overall_score: 80 },
      ],
    });

    renderWithRouter(<Projects />);

    expect(await screen.findByText("Billing API")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/search by project/i), { target: { value: "website" } });

    expect(screen.queryByText("Billing API")).not.toBeInTheDocument();
    expect(screen.getByText("Website")).toBeInTheDocument();
  });

  it("does not open a report for a running project", async () => {
    getProjects.mockResolvedValueOnce({
      projects: [
        { project_id: "running", project_name: "Worker", language: "Python", status: "running", progress: 40, current_stage: "Security Agent", source_type: "github" },
      ],
    });

    renderWithRouter(<Projects />);

    fireEvent.click(await screen.findByText("Worker"));

    expect(getReport).not.toHaveBeenCalled();
    expect(screen.getByText(/report will be available/i)).toBeInTheDocument();
  });
});
