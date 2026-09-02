import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CompareReports from "./CompareReports";
import { renderWithRouter } from "../../test/test-utils";
import { compareReports } from "../../api/client";

vi.mock("../../api/client", () => ({
  compareReports: vi.fn(),
}));

const reports = [
  { project_id: "one", project_name: "Redux", overall_score: 76.61, quality_score: 80, security_score: 90, test_score: 60 },
  { project_id: "two", project_name: "Express", overall_score: 72.83, quality_score: 82, security_score: 90, test_score: null },
  { project_id: "three", project_name: "Redux", overall_score: 76.61, quality_score: 80, security_score: 90, test_score: 60 },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CompareReports", () => {
  it("requires two different reports before comparing", async () => {
    renderWithRouter(<CompareReports reports={reports} />);

    fireEvent.click(screen.getByRole("button", { name: /compare/i }));

    expect(await screen.findByText("Select two reports before comparing.")).toBeInTheDocument();
    expect(compareReports).not.toHaveBeenCalled();
  });

  it("renders comparison direction when the second report is lower, higher, equal and missing", async () => {
    compareReports.mockResolvedValueOnce({
      comparison: {
        first: reports[0],
        second: reports[1],
        first_label: "Redux",
        second_label: "Express",
        metrics: [
          {
            key: "overall_score",
            label: "Overall Score",
            first_value: 76.61,
            second_value: 72.83,
            direction: "second_lower",
            absolute_delta: 3.78,
            summary: "Express is 3.78 points lower than Redux.",
          },
          {
            key: "quality_score",
            label: "Quality Score",
            first_value: 80,
            second_value: 82,
            direction: "second_higher",
            absolute_delta: 2,
            summary: "Express is 2 points higher than Redux.",
          },
          {
            key: "security_score",
            label: "Security Score",
            first_value: 90,
            second_value: 90,
            direction: "equal",
            absolute_delta: 0,
            summary: "Redux and Express are equal for security score.",
          },
          {
            key: "test_score",
            label: "Testing Score",
            first_value: 60,
            second_value: null,
            direction: "missing",
            absolute_delta: null,
            summary: "Testing Score is unavailable for one or both reports.",
          },
        ],
      },
    });
    renderWithRouter(<CompareReports reports={reports} />);

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "one" } });
    fireEvent.change(selects[1], { target: { value: "two" } });
    fireEvent.click(screen.getByRole("button", { name: /compare/i }));

    await waitFor(() => expect(compareReports).toHaveBeenCalledWith("one", "two"));
    expect(screen.getByText("Express is 3.78 points lower than Redux.")).toBeInTheDocument();
    expect(screen.getByText("Express is 2 points higher than Redux.")).toBeInTheDocument();
    expect(screen.getByText("Redux and Express are equal for security score.")).toBeInTheDocument();
    expect(screen.getByText("Testing Score is unavailable for one or both reports.")).toBeInTheDocument();
    expect(screen.queryByText("-3.78")).not.toBeInTheDocument();
  });

  it("disambiguates duplicate report names in fallback comparisons", async () => {
    compareReports.mockResolvedValueOnce({
      comparison: { delta: { overall: 0, quality: 0, security: 0, testing: 0 } },
    });
    renderWithRouter(<CompareReports reports={reports} />);

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "one" } });
    fireEvent.change(selects[1], { target: { value: "three" } });
    fireEvent.click(screen.getByRole("button", { name: /compare/i }));

    await waitFor(() => expect(compareReports).toHaveBeenCalledWith("one", "three"));
    expect(await screen.findByText("Redux (one)")).toBeInTheDocument();
    expect(screen.getByText("Redux (three)")).toBeInTheDocument();
  });
});
