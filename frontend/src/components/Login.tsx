import { useState, FormEvent } from 'react'

interface LoginProps {
  onLogin: () => void
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    backgroundColor: '#1a1a2e',
  } as React.CSSProperties,
  card: {
    backgroundColor: '#16213e',
    borderRadius: '12px',
    padding: '40px',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    width: '360px',
  } as React.CSSProperties,
  title: {
    color: '#e94560',
    fontSize: '28px',
    fontWeight: 'bold',
    textAlign: 'center' as const,
    marginBottom: '8px',
  } as React.CSSProperties,
  subtitle: {
    color: '#8892b0',
    fontSize: '14px',
    textAlign: 'center' as const,
    marginBottom: '32px',
  } as React.CSSProperties,
  inputGroup: {
    marginBottom: '20px',
  } as React.CSSProperties,
  label: {
    display: 'block',
    color: '#ccd6f6',
    fontSize: '14px',
    marginBottom: '8px',
  } as React.CSSProperties,
  input: {
    width: '100%',
    padding: '12px 16px',
    backgroundColor: '#0f3460',
    border: '1px solid #1a4b8c',
    borderRadius: '8px',
    color: '#ccd6f6',
    fontSize: '16px',
    outline: 'none',
    transition: 'border-color 0.2s',
    boxSizing: 'border-box' as const,
  } as React.CSSProperties,
  button: {
    width: '100%',
    padding: '14px',
    backgroundColor: '#e94560',
    border: 'none',
    borderRadius: '8px',
    color: '#fff',
    fontSize: '16px',
    fontWeight: 'bold',
    cursor: 'pointer',
    transition: 'background-color 0.2s',
    marginTop: '12px',
  } as React.CSSProperties,
  error: {
    color: '#ff6b6b',
    fontSize: '14px',
    textAlign: 'center' as const,
    marginTop: '16px',
  } as React.CSSProperties,
}

export function Login({ onLogin }: LoginProps) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!password.trim()) {
      setError('请输入密码')
      return
    }

    setLoading(true)
    setError('')

    try {
      const response = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })

      const data = await response.json()

      if (data.success) {
        localStorage.setItem('wxeye_authenticated', 'true')
        onLogin()
      } else {
        setError(data.message || '密码错误')
      }
    } catch {
      setError('网络错误，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>WxEye</h1>
        <p style={styles.subtitle}>WeChat Visual Monitor</p>

        <form onSubmit={handleSubmit}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>访问密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              placeholder="请输入密码"
              autoFocus
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            style={{
              ...styles.button,
              opacity: loading ? 0.7 : 1,
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
            disabled={loading}
          >
            {loading ? '验证中...' : '登录'}
          </button>
        </form>

        {error && <p style={styles.error}>{error}</p>}
      </div>
    </div>
  )
}
