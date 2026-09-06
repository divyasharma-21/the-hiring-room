import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { api, getToken, setToken } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null)
      setLoading(false)
      return null
    }
    try {
      const data = await api('/auth/me')
      setUser(data.user)
      return data.user
    } catch {
      setToken(null)
      setUser(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const login = async (email, password) => {
    const data = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setToken(data.token)
    setUser(data.user)
    return data.user
  }

  const register = async (email, password, full_name) => {
    const data = await api('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name }),
    })
    setToken(data.token)
    setUser(data.user)
    return data.user
  }

  const logout = () => {
    setToken(null)
    setUser(null)
  }

  const updateProfile = async (patch) => {
    const data = await api('/auth/profile', {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
    setUser(data.user)
    return data.user
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh, updateProfile }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
