import { authMessageFromSearch } from "./Login.helpers";
import "./Login.css";

interface LoginProps {
  onLogin: () => void;
}

function Login({ onLogin }: LoginProps) {
  const error = authMessageFromSearch(window.location.search);
  return (
    <div className="login-container">
      <div className="login-card">
        <h1>Pigify</h1>
        {error ? (
          <p className="login-error" role="alert">
            {error}
          </p>
        ) : (
          <p>Connect your Spotify account to get started</p>
        )}
        <button type="button" className="login-button" onClick={onLogin}>
          Login with Spotify
        </button>
      </div>
    </div>
  );
}

export default Login;
