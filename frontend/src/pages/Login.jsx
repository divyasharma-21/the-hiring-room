import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { Sparkles } from 'lucide-react'
import { t, getStoredLanguage } from '../i18n'

export default function Login({ lang }) {
  const L = lang || getStoredLanguage()
  const tr = (k) => t(k, L)
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email.trim(), password)
      navigate('/app')
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-visual">
        <div className="auth-visual-inner">
          <div className="brand-mark lg">TH</div>
          <h2>{tr('yourAiRoom')}</h2>
          <p>{tr('yourAiRoomSub')}</p>
          <ul className="auth-bullets">
            <li><Sparkles size={14} /> {tr('authBullet1')}</li>
            <li><Sparkles size={14} /> {tr('authBullet2')}</li>
            <li><Sparkles size={14} /> {tr('authBullet3')}</li>
          </ul>
        </div>
      </div>
      <div className="auth-form-wrap">
        <form className="auth-card" onSubmit={onSubmit}>
          <h1>{tr('welcomeBack')}</h1>
          <p className="muted">{tr('loginSub')}</p>
          {error && <div className="error-box">{error}</div>}
          <label>
            {tr('email')}
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" />
          </label>
          <label>
            {tr('password')}
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" autoComplete="current-password" />
          </label>
          <button className="btn btn-primary btn-block" disabled={loading} type="submit">
            {loading ? tr('signingIn') : tr('loginBtn')}
          </button>
          <p className="auth-switch">
            {tr('newHere')} <Link to="/signup">{tr('createAccount')}</Link>
          </p>
          <p className="auth-switch"><Link to="/">{tr('backHome')}</Link></p>
        </form>
      </div>
    </div>
  )
}
