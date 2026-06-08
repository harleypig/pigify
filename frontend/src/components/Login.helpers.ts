// Pure helper for Login: map the URL query string to an auth message.

const AUTH_MESSAGES: Record<string, string> = {
  not_authorized: "This Spotify account isn't allowed to use this instance.",
  demo_invalid: "This demo link is invalid, expired, or already used.",
  demo_failed: "Something went wrong starting the demo. Try again later.",
};

/**
 * The auth-failure message to show on the login screen, or null. Driven by
 * the `?error=` param the backend redirects to when a login is rejected (the
 * access gate) or a demo invite can't be redeemed.
 */
export function authMessageFromSearch(search: string): string | null {
  const error = new URLSearchParams(search).get("error");
  return (error && AUTH_MESSAGES[error]) || null;
}
