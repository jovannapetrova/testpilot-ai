import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CompareReports from "./CompareReports";
import { renderWithRouter } from "../../test/test-utils";
import { compareReports } from "../../api/client";

vi.mock("../../api/client", () => ({
  compareReports: vi.fn(),
}));

const reports = [
  { project_id: "one", project_name: "First" },
  { project_id: "two", project_name: "Second" },
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

  it("renders comparison deltas returned by the API", async () => {
    compareReports.mockResolvedValueOnce({
      comparison: { delta: { overall: 5, quality: -2, security: 0, testing: 4 } },
    });
    renderWithRouter(<CompareReports reports={reports} />);

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "one" } });
    fireEvent.change(selects[1], { target: { value: "two" } });
    fireEvent.click(screen.getByRole("button", { name: /compare/i }));

    await waitFor(() => expect(compareReports).toHaveBeenCalledWith("one", "two"));
    expect(screen.getByText("+5")).toBeInTheDocument();
    expect(screen.getByText("-2")).toBeInTheDocument();
  });
});
