import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Projects from "./Projects";
import { renderWithRouter } from "../test/test-utils";
import { deleteProjectAnalysis, getProjects, getReport } from "../api/client";

vi.mock("../api/client", () => ({
  deleteProjectAnalysis: vi.fn(),
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

  it("confirms and cancels project archive deletion", async () => {
    getProjects.mockResolvedValueOnce({
      projects: [
        { project_id: "failed-one", project_name: "Failed API", language: "Python", status: "failed", source_type: "github", error: "Clone failed" },
      ],
    });

    renderWithRouter(<Projects />);

    fireEvent.click(await screen.findByRole("button", { name: /delete analysis failed api/i }));
    expect(screen.getByText("Delete this analysis?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(deleteProjectAnalysis).not.toHaveBeenCalled();
    expect(screen.getByText("Failed API")).toBeInTheDocument();
  });

  it("removes a project archive card after successful deletion", async () => {
    getProjects.mockResolvedValueOnce({
      projects: [
        { project_id: "failed-two", project_name: "Failed Worker", language: "Python", status: "failed", source_type: "upload", error: "Analysis failed" },
      ],
    });
    deleteProjectAnalysis.mockResolvedValueOnce({ success: true });

    renderWithRouter(<Projects />);

    fireEvent.click(await screen.findByRole("button", { name: /delete analysis failed worker/i }));
    fireEvent.click(screen.getByRole("button", { name: /^delete analysis$/i }));

    await waitFor(() => expect(deleteProjectAnalysis).toHaveBeenCalledWith("failed-two"));
    expect(screen.queryByText("Failed Worker")).not.toBeInTheDocument();
    expect(screen.getByText("Analysis deleted.")).toBeInTheDocument();
  });

  it("keeps the project card and shows an error when deletion fails", async () => {
    getProjects.mockResolvedValueOnce({
      projects: [
        { project_id: "failed-three", project_name: "Failed Service", language: "Python", status: "failed", source_type: "upload", error: "Analysis failed" },
      ],
    });
    deleteProjectAnalysis.mockRejectedValueOnce({ userMessage: "Unable to delete this analysis." });

    renderWithRouter(<Projects />);

    fireEvent.click(await screen.findByRole("button", { name: /delete analysis failed service/i }));
    fireEvent.click(screen.getByRole("button", { name: /^delete analysis$/i }));

    await waitFor(() => expect(deleteProjectAnalysis).toHaveBeenCalledWith("failed-three"));
    expect(screen.getByText("Failed Service")).toBeInTheDocument();
    expect(screen.getByText("Unable to delete this analysis.")).toBeInTheDocument();
  });

  it("does not allow deleting queued or running analyses from the archive", async () => {
    getProjects.mockResolvedValueOnce({
      projects: [
        { project_id: "running", project_name: "Live Worker", language: "Python", status: "running", progress: 40, current_stage: "Security Agent", source_type: "github" },
      ],
    });

    renderWithRouter(<Projects />);

    const deleteButton = await screen.findByRole("button", { name: /delete analysis live worker/i });
    expect(deleteButton).toBeDisabled();
    expect(deleteButton).toHaveAttribute("title", expect.stringMatching(/queued or running/i));
    expect(deleteProjectAnalysis).not.toHaveBeenCalled();
  });
});
