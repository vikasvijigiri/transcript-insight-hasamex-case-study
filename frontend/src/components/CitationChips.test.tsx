import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CitationChips from "./CitationChips";

describe("CitationChips", () => {
  it("warns when there are no citations, since an ungrounded claim must be visibly flagged", () => {
    render(<CitationChips citations={[]} />);
    expect(screen.getByText(/no direct quote found/i)).toBeInTheDocument();
  });

  it("renders the exact quote and timestamp for each citation", () => {
    render(
      <CitationChips
        citations={[
          { expert_id: "france", expert_name: "Dr. Jean Martin", quote: "Adoption is growing", timestamp: "00:18" },
        ]}
      />,
    );
    expect(screen.getByText("00:18")).toBeInTheDocument();
    expect(screen.getByText(/Dr\. Jean Martin/)).toBeInTheDocument();
    expect(screen.getByText(/Adoption is growing/)).toBeInTheDocument();
  });

  it("renders one chip per citation, in order, when a claim is backed by multiple experts", () => {
    render(
      <CitationChips
        citations={[
          { expert_id: "france", expert_name: "Dr. Jean Martin", quote: "quote one", timestamp: "00:18" },
          { expert_id: "germany", expert_name: "Anna Keller", quote: "quote two", timestamp: "01:10" },
        ]}
      />,
    );
    expect(screen.getByText(/quote one/)).toBeInTheDocument();
    expect(screen.getByText(/quote two/)).toBeInTheDocument();
  });
});
