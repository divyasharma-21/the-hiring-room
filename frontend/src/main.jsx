import { StrictMode, useState, useEffect, Component } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import { AuthProvider, useAuth } from './AuthContext'
import { getStoredLanguage, setStoredLanguage } from './i18n'
import Layout from './Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Interviews from './pages/Interviews'
import Performance from './pages/Performance'
import HistoryPage from './pages/History'
import Profile from './pages/Profile'
import Settings from './pages/Settings'
import App from './App'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="auth-page" style={{ placeItems: 'center' }}>
        <div className="loading"><span className="spinner" /> Loading…</div>
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return children
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (user) return <Navigate to="/app" replace />
  return children
}

function Root() {
  const [lang, setLang] = useState(() => getStoredLanguage())
  useEffect(() => { setStoredLanguage(lang) }, [lang])

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<PublicOnly><Landing lang={lang} setLang={setLang} /></PublicOnly>} />
          <Route path="/login" element={<PublicOnly><Login lang={lang} /></PublicOnly>} />
          <Route path="/signup" element={<PublicOnly><Signup lang={lang} /></PublicOnly>} />
          <Route
            path="/app"
            element={
              <PrivateRoute>
                <Layout lang={lang} setLang={setLang} />
              </PrivateRoute>
            }
          >
            <Route index element={<Dashboard lang={lang} />} />
            <Route path="resume" element={<App lang={lang} setLang={setLang} embed />} />
            <Route path="interviews" element={<Interviews lang={lang} />} />
            <Route path="workspace" element={<App lang={lang} setLang={setLang} embed />} />
            <Route path="performance" element={<Performance lang={lang} />} />
            <Route path="history" element={<HistoryPage lang={lang} />} />
            <Route path="history/:sessionId" element={<HistoryPage lang={lang} />} />
            <Route path="profile" element={<Profile lang={lang} />} />
            <Route path="settings" element={<Settings lang={lang} setLang={setLang} />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }
  static getDerivedStateFromError(error) {
    return { error }
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, fontFamily: 'system-ui', maxWidth: 640, margin: '40px auto' }}>
          <h1>Something went wrong</h1>
          <p style={{ color: '#666' }}>{String(this.state.error?.message || this.state.error)}</p>
          <button type="button" onClick={() => window.location.href = '/'} style={{ padding: '10px 16px', marginTop: 12 }}>
            Go home
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <Root />
    </ErrorBoundary>
  </StrictMode>,
)
