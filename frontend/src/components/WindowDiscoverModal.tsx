import React, { useState } from 'react'

interface WindowInfo {
  name: string
  x: number
  y: number
  width: number
  height: number
}

interface WindowDiscoverModalProps {
  isOpen: boolean
  onClose: () => void
  onAddContact: (name: string) => void
}

export function WindowDiscoverModal({
  isOpen,
  onClose,
  onAddContact,
}: WindowDiscoverModalProps) {
  const [windows, setWindows] = useState<WindowInfo[]>([])
  const [loading, setLoading] = useState(false)

  const handleDiscover = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/wechat/windows')
      const data = await res.json()
      setWindows(data.windows || [])
    } catch (err) {
      console.error('发现窗口失败:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = (name: string) => {
    onAddContact(name)
  }

  if (!isOpen) return null

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>发现微信窗口</h2>
          <button onClick={onClose} style={styles.closeButton}>
            ×
          </button>
        </div>

        <div style={styles.content}>
          <div style={styles.actions}>
            <button onClick={handleDiscover} disabled={loading} style={styles.discoverButton}>
              {loading ? '扫描中...' : '扫描窗口'}
            </button>
            <span style={styles.hint}>点击扫描获取当前打开的微信聊天窗口</span>
          </div>

          <div style={styles.windowList}>
            {windows.length === 0 ? (
              <div style={styles.placeholder}>
                {loading ? '正在扫描...' : '点击"扫描窗口"按钮开始'}
              </div>
            ) : (
              windows.map((win) => (
                <div key={win.name} style={styles.windowItem}>
                  <div style={styles.windowInfo}>
                    <span style={styles.windowName}>{win.name}</span>
                    <span style={styles.windowSize}>
                      {win.width} × {win.height}
                    </span>
                  </div>
                  <button onClick={() => handleAdd(win.name)} style={styles.addButton}>
                    添加
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        <div style={styles.footer}>
          <span style={styles.count}>
            {windows.length > 0 ? `发现 ${windows.length} 个窗口` : ''}
          </span>
        </div>
      </div>
    </div>
  )
}

const styles: { [key: string]: React.CSSProperties } = {
  overlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    backgroundColor: '#1a1a2e',
    borderRadius: '8px',
    width: '500px',
    maxHeight: '70%',
    display: 'flex',
    flexDirection: 'column',
    border: '1px solid #0f3460',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    borderBottom: '1px solid #0f3460',
  },
  title: {
    margin: 0,
    fontSize: '18px',
    fontWeight: 600,
    color: '#fff',
  },
  closeButton: {
    background: 'none',
    border: 'none',
    color: '#888',
    fontSize: '24px',
    cursor: 'pointer',
    padding: '0 8px',
  },
  content: {
    flex: 1,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  actions: {
    padding: '16px 20px',
    borderBottom: '1px solid #0f3460',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  discoverButton: {
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: 600,
    backgroundColor: '#4caf50',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  hint: {
    fontSize: '13px',
    color: '#888',
  },
  windowList: {
    flex: 1,
    overflowY: 'auto',
    padding: '12px 20px',
  },
  placeholder: {
    textAlign: 'center',
    padding: '40px',
    color: '#666',
  },
  windowItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    backgroundColor: '#0f3460',
    borderRadius: '4px',
    marginBottom: '8px',
  },
  windowInfo: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  windowName: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#fff',
  },
  windowSize: {
    fontSize: '12px',
    color: '#888',
  },
  addButton: {
    padding: '6px 16px',
    fontSize: '13px',
    fontWeight: 600,
    backgroundColor: '#1a4b8c',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  footer: {
    padding: '12px 20px',
    borderTop: '1px solid #0f3460',
  },
  count: {
    fontSize: '13px',
    color: '#888',
  },
}
