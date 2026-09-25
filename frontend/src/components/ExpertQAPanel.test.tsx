import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ExpertQAPanel from "./ExpertQAPanel";

const { expertQA, transcript } = vi.hoisted(() => ({ expertQA: vi.fn(), transcript: vi.fn() }));

vi.mock("@/lib/api", () => ({ api: { expertQA, transcript } }));

const experts = [
  { id: "france", name: "Dr. Jean Martin", role: "Head of Urology", market: "France" },
  { id: "germany", name: "Anna Keller", role: "Procurement Director", market: "Germany" },
];

function response(id: string, name: string, market: string) {
  return {
    expert_id: id,
    expert_name: name,
    role: "Role",
    market,
    answers: [{ question: "How is adoption?", answer: `${market} answer`, citations: [] }],
  };
}

describe("ExpertQAPanel", () => {
  beforeEach(() => {
    expertQA.mockReset();
    transcript.mockReset();
  });

  it("keeps the latest selected source visible after its request resolves", async () => {
    expertQA.mockImplementation((id: string) =>
      Promise.resolve(
        id === "france"
          ? response("france", "Dr. Jean Martin", "France")
          : response("germany", "Anna Keller", "Germany"),
      ),
    );

    render(<ExpertQAPanel experts={experts} />);
    expect(await screen.findByText("France answer")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Anna Keller/i }));

    await waitFor(() => expect(screen.getByText("Germany answer")).toBeInTheDocument());
    expect(expertQA).toHaveBeenCalledWith("germany", expect.any(AbortSignal));
  });

  it("opens the cited passage in a dialog when the side inspector is hidden", async () => {
    // jsdom has no matchMedia, which behaves like a laptop-width window where
    // the xl-only evidence rail is not displayed.
    const citation = {
      expert_id: "france",
      expert_name: "Dr. Jean Martin",
      quote: "budget approval takes a year",
      timestamp: "01:20",
    };
    expertQA.mockResolvedValue({
      ...response("france", "Dr. Jean Martin", "France"),
      answers: [{ question: "How is adoption?", answer: "France answer", citations: [citation] }],
    });
    transcript.mockResolvedValue({
      expert_id: "france",
      raw_text: "01:20\nExpert: The budget approval takes a year here.",
    });

    render(<ExpertQAPanel experts={experts} />);
    fireEvent.click(await screen.findByRole("button", { name: /Inspect evidence/i }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getAllByText("budget approval takes a year").some((node) => node.tagName === "MARK")).toBe(
        true,
      ),
    );
  });
});
