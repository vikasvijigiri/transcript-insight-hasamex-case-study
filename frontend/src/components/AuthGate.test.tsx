import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
    },
  },
  googleAuthorizationUrl: vi.fn(() => "https://example.supabase.co/auth/v1/authorize?provider=google"),
}));

import AuthGate from "./AuthGate";

describe("AuthGate", () => {
  it("explains the research value before sign-in and offers the protected Google flow", () => {
    render(
      <AuthGate>
        <p>Protected workspace</p>
      </AuthGate>,
    );

    expect(screen.getByText(/robotic surgery/i)).toBeInTheDocument();
    expect(screen.getByText(/decision-ready reading/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /continue with google/i })).toHaveAttribute(
      "href",
      expect.stringContaining("provider=google"),
    );
    expect(screen.queryByText("Protected workspace")).not.toBeInTheDocument();
  });
});
