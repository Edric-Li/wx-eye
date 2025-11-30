import { useState, useEffect } from 'react'
import { Monitor } from './components/Monitor'
import { Login } from './components/Login'

// Global styles
const globalStyles = `
  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    padding: 0;
    background-color: #1a1a2e;
  }

  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  ::-webkit-scrollbar-track {
    background: #0f3460;
  }

  ::-webkit-scrollbar-thumb {
    background: #1a4b8c;
    border-radius: 4px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: #2a5b9c;
  }
`

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    // 检查本地存储的认证状态
    const auth = localStorage.getItem('wxeye_authenticated')
    setIsAuthenticated(auth === 'true')
  }, [])

  const handleLogin = () => {
    setIsAuthenticated(true)
  }

  // 加载中状态
  if (isAuthenticated === null) {
    return (
      <>
        <style>{globalStyles}</style>
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          color: '#8892b0',
        }}>
          加载中...
        </div>
      </>
    )
  }

  return (
    <>
      <style>{globalStyles}</style>
      {isAuthenticated ? <Monitor /> : <Login onLogin={handleLogin} />}
    </>
  )
}

export default App
