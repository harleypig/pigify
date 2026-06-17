import { useState } from "react";
import logoUrl from "../assets/pigify-logo.png";
import { flipTheme, resolveOwnerDefault } from "../lib/ownerTheme";
import { authMessageFromSearch } from "./Login.helpers";
import { OwnerThemeToggle } from "./OwnerThemeToggle";
import "./Login.css";

interface LoginProps {
  onLogin: () => void | Promise<void>;
}

// Stable keys for the decorative equalizer bars (CSS drives their height
// and stagger via :nth-child — see Login.css).
const EQ_BARS = ["b1", "b2", "b3", "b4", "b5", "b6", "b7"] as const;

function Login({ onLogin }: LoginProps) {
  const urlError = authMessageFromSearch(window.location.search);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  // Owner-surface theme: starts from the owner default each mount and is
  // never persisted (ephemeral). Scoped to the .login subtree below via
  // data-theme, so it's independent of the user's pigify.theme.
  const [ownerTheme, setOwnerTheme] = useState(resolveOwnerDefault);

  // A failed sign-in attempt (e.g. the backend is unreachable) takes
  // precedence over a redirect-driven error from the URL.
  const error = connectError ?? urlError;

  const handleConnect = async () => {
    setConnectError(null);
    setConnecting(true);
    try {
      await onLogin();
      // On success the browser navigates to Spotify; leave the button in
      // its connecting state until then.
    } catch (err) {
      setConnectError(
        err instanceof Error && err.message
          ? err.message
          : "Couldn't start sign-in. Try again.",
      );
      setConnecting(false);
    }
  };

  return (
    <div className="login" data-theme={ownerTheme}>
      <div className="login__veil" aria-hidden="true" />

      <main className="console" aria-labelledby="console-wordmark">
        <div className="console__bezel" aria-hidden="true" />

        <OwnerThemeToggle
          theme={ownerTheme}
          onToggle={() => setOwnerTheme(flipTheme)}
        />

        <div className="console__lockup">
          <img
            className={`console__logo${error ? " is-error" : ""}`}
            src={logoUrl}
            alt=""
            width={120}
            height={128}
          />
          <h1 id="console-wordmark" className="console__wordmark">
            pigify
          </h1>
        </div>

        <p className="console__kicker">Personal Spotify console</p>

        <div className="console__eq" aria-hidden="true">
          {EQ_BARS.map((id) => (
            <span key={id} />
          ))}
        </div>

        <p
          className={`console__status${error ? " is-error" : ""}`}
          role={error ? "alert" : undefined}
        >
          {error ? (
            <>
              <span className="console__tag">SIGNAL LOST</span>
              <span>{error}</span>
            </>
          ) : (
            <>
              <span className="console__tag">READY</span>
              <span>awaiting handshake</span>
              <span className="console__caret" aria-hidden="true" />
            </>
          )}
        </p>

        <button
          type="button"
          className="console__connect"
          onClick={handleConnect}
          disabled={connecting}
        >
          <span className="console__led" aria-hidden="true" />
          {connecting ? "Connecting…" : "Connect Spotify"}
        </button>

        <p className="console__fine">
          Your library, your rules — smart mixes, scrobbles, and playlists that
          run on YAML.
        </p>

        <p className="console__powered">Powered by Spotify</p>
      </main>
    </div>
  );
}

export default Login;
