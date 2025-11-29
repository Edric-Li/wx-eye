import React from 'react'
import { LogMessage } from '../hooks/useWebSocket'

interface LogPanelProps {
  logs: LogMessage[]
}

export function LogPanel({ logs }: LogPanelProps) {
  const getLevelColor = (level: string) => {
    switch (level) {
      case 'error':
        return '#f44336'
      case 'warning':
        return '#ff9800'
      case 'info':
      default:
        return '#4caf50'
    }
  }

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'error':
        return '✕'
      case 'warning':
        return '⚠'
      case 'info':
      default:
        return 'ℹ'
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h3 style={styles.title}>日志</h3>
        <span style={styles.count}>{logs.length}</span>
      </div>

      <div style={styles.logList}>
        {logs.length === 0 ? (
          <div style={styles.placeholder}>暂无日志</div>
        ) : (
          logs.map((log, index) => (
            <div key={`${log.timestamp}-${index}`} style={styles.logItem}>
              <span
                style={{
                  ...styles.levelIcon,
                  color: getLevelColor(log.level),
                }}
              >
                {getLevelIcon(log.level)}
              </span>
              <span style={styles.time}>{new Date(log.timestamp).toLocaleTimeString()}</span>
              <span style={styles.message}>{log.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px',
    borderBottom: '1px solid #0f3460',
  },
  title: {
    margin: 0,
    fontSize: '18px',
    fontWeight: 600,
  },
  count: {
    backgroundColor: '#0f3460',
    padding: '4px 12px',
    borderRadius: '12px',
    fontSize: '12px',
  },
  logList: {
    flex: 1,
    overflowY: 'auto',
    padding: '8px',
    maxHeight: 'calc(100vh - 300px)',
  },
  placeholder: {
    textAlign: 'center',
    padding: '24px',
    color: '#666',
  },
  logItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    padding: '8px',
    borderBottom: '1px solid #0f3460',
    fontSize: '13px',
  },
  levelIcon: {
    flexShrink: 0,
    width: '16px',
    textAlign: 'center',
  },
  time: {
    flexShrink: 0,
    color: '#666',
    fontFamily: 'monospace',
    fontSize: '12px',
  },
  message: {
    flex: 1,
    color: '#ccc',
    wordBreak: 'break-word',
  },
}
