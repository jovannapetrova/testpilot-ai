import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AgentTimeline from "./AgentTimeline";
import { renderWithRouter } from "../../test/test-utils";

describe("AgentTimeline", () => {
  it("shows idle system state instead of historical completed badges when no run is active", () => {
    renderWithRouter(
      <AgentTimeline
        running={false}
        logs={[
          { name: "Project Detector Agent", status: "completed", message: "Completed successfully" },
          { name: "Security Agent", status: "completed", message: "Completed successfully" },
        ]}
      />,
    );

    expect(screen.getByText("System state: Ready")).toBeInTheDocument();
    expect(screen.getByText("Last run: 2/2 agents completed.")).toBeInTheDocument();
    expect(screen.queryByText("Completed successfully")).not.toBeInTheDocument();
  });

  it("shows live agent detail when analysis is running", () => {
    renderWithRouter(
      <AgentTimeline
        running
        logs={[
          { name: "Project Detector Agent", status: "completed", message: "Completed successfully" },
          { name: "Security Agent", status: "running", message: "Running" },
        ]}
      />,
    );

    expect(screen.getByText("Analyzing")).toBeInTheDocument();
    expect(screen.getByText("Security Agent")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
  });
});
