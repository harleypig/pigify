import './Login.css'

interface LoginProps {
  onLogin: () => void
}

function Login({ onLogin }: LoginProps) {
  return (
    <div className="login-container">
      <div className="login-card">
        <h1>Pigify</h1>
        <p>Connect your Spotify account to get started</p>
        <button className="login-button" onClick={onLogin}>
          Login with Spotify
        </button>
      </div>
    </div>
  )
}

export default Login

