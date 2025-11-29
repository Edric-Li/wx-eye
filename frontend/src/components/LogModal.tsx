import React, { useEffect, useRef } from 'react'
import { RawLogMessage } from '../hooks/useWebSocket'

interface LogModalProps {
  isOpen: boolean
  onClose: () => void
  logs: RawLogMessage[]
  onSubscribe: () => void
  onUnsubscribe: () => void
}

export function LogModal({ isOpen, onClose, logs, onSubscribe, onUnsubscribe }: LogModalProps) {
  const listRef = useRef<HTMLDivElement>(null)
  const autoScrollRef = useRef(true)

  // 打开时订阅日志
  useEffect(() => {
    if (isOpen) {
      onSubscribe()
    } else {
      onUnsubscribe()
    }
  }, [isOpen, onSubscribe, onUnsubscribe])

  // 自动滚动到底部
  useEffect(() => {
    if (listRef.current && autoScrollRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [logs.length])

  const handleScroll = () => {
    if (!listRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = listRef.current
    // 如果用户滚动到接近底部，启用自动滚动
    autoScrollRef.current = scrollHeight - scrollTop - clientHeight < 50
  }

  const getLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'error':
        return '#f44336'
      case 'warning':
        return '#ff9800'
      case 'debug':
        return '#888'
      case 'info':
      default:
        return '#4caf50'
    }
  }

  if (!isOpen) return null

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>后台日志</h2>
          <button onClick={onClose} style={styles.closeButton}>
            ×
          </button>
        </div>

        <div style={styles.logList} ref={listRef} onScroll={handleScroll}>
          {logs.length === 0 ? (
            <div style={styles.placeholder}>等待日志...</div>
          ) : (
            logs.map((log, index) => (
              <div key={`${log.timestamp}-${index}`} style={styles.logItem}>
                <span style={styles.timestamp}>
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <span
                  style={{
                    ...styles.level,
                    color: getLevelColor(log.level),
                  }}
                >
                  [{log.level.toUpperCase()}]
                </span>
                <span style={styles.logger}>{log.logger}</span>
                <span style={styles.message}>{log.message}</span>
              </div>
            ))
          )}
        </div>

        <div style={styles.footer}>
          <span style={styles.count}>{logs.length} 条日志</span>
          <button
            onClick={() => {
              autoScrollRef.current = true
              if (listRef.current) {
                listRef.current.scrollTop = listRef.current.scrollHeight
              }
            }}
            style={styles.scrollButton}
          >
            滚动到底部
          </button>
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
    width: '80%',
    maxWidth: '900px',
    height: '70%',
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
  logList: {
    flex: 1,
    overflowY: 'auto',
    padding: '8px',
    fontFamily: 'Monaco, Consolas, "Courier New", monospace',
    fontSize: '12px',
  },
  placeholder: {
    textAlign: 'center',
    padding: '40px',
    color: '#666',
  },
  logItem: {
    display: 'flex',
    gap: '8px',
    padding: '4px 8px',
    borderBottom: '1px solid #0f3460',
    alignItems: 'flex-start',
    lineHeight: 1.4,
  },
  timestamp: {
    color: '#666',
    flexShrink: 0,
  },
  level: {
    flexShrink: 0,
    fontWeight: 600,
    width: '70px',
  },
  logger: {
    color: '#888',
    flexShrink: 0,
    maxWidth: '150px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  message: {
    color: '#ccc',
    flex: 1,
    wordBreak: 'break-word',
    whiteSpace: 'pre-wrap',
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 20px',
    borderTop: '1px solid #0f3460',
  },
  count: {
    color: '#888',
    fontSize: '13px',
  },
  scrollButton: {
    padding: '6px 12px',
    fontSize: '12px',
    backgroundColor: '#0f3460',
    color: '#aaa',
    border: '1px solid #1a4b8c',
    borderRadius: '4px',
    cursor: 'pointer',
  },
}
