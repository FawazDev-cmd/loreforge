import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "../feedback/EmptyState";
import { ErrorState } from "../feedback/ErrorState";
import { LoadingState } from "../feedback/LoadingState";
import { StatusIndicator } from "../feedback/StatusIndicator";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Input } from "./Input";

describe("shared UI foundation", () => {
  it("renders an accessible button", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders link buttons for route actions", () => {
    render(
      <MemoryRouter>
        <Button as={Link} to="/workspace">
          Workspace
        </Button>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Workspace" })).toHaveAttribute("href", "/workspace");
  });

  it("connects input help and error text", () => {
    render(<Input error="Required" helpText="Use a bearer token." label="API key" />);

    const input = screen.getByLabelText("API key");
    expect(input).toHaveAccessibleDescription("Use a bearer token. Required");
    expect(input).toHaveAttribute("aria-invalid", "true");
  });

  it("renders reusable feedback and status states", () => {
    render(
      <>
        <Badge tone="success">Ready</Badge>
        <StatusIndicator tone="warning">Degraded</StatusIndicator>
        <EmptyState title="Empty" message="Nothing loaded." />
        <ErrorState title="Error" message="Try again." />
        <LoadingState message="Loading data." />
      </>,
    );

    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Degraded")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Empty" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Error" })).toBeInTheDocument();
    expect(screen.getByText("Loading data.")).toBeInTheDocument();
  });
});