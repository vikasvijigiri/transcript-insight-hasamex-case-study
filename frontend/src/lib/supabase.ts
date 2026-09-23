import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/**
 * Undefined is intentional in local/demo mode: it keeps the app usable without
 * an account while production turns on AUTH_REQUIRED at the API boundary.
 */
export const supabase: SupabaseClient | null =
  url && anonKey ? createClient(url, anonKey) : null;

export const authenticationConfigured = Boolean(supabase);

/** Browser-navigation fallback when an extension blocks the SDK's OAuth fetch. */
export function googleAuthorizationUrl(redirectTo?: string): string | null {
  if (!url) return null;
  const authorizationUrl = new URL("/auth/v1/authorize", url);
  authorizationUrl.searchParams.set("provider", "google");
  if (redirectTo) authorizationUrl.searchParams.set("redirect_to", redirectTo);
  return authorizationUrl.toString();
}
