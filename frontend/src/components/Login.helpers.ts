// Pure helper for Login: map the URL query string to an auth message.

/**
 * The auth-failure message to show on the login screen, or null. Driven by
 * the `?error=` param the backend redirects to when the access gate rejects
 * a login.
 */
export function authMessageFromSearch(search: string): string | null {
  const params = new URLSearchParams(search);
  if (params.get("error") === "not_authorized") {
    return "This Spotify account isn't allowed to use this instance.";
  }
  return null;
}
