import React, { useState, useMemo } from 'react'
import { useWebSocket, ScreenshotMessage, ContactStatus } from '../hooks/useWebSocket'
import { ImageViewer } from './ImageViewer'
import { LogPanel } from './LogPanel'
import { AIMessagePanel } from './AIMessagePanel'
import { SendMessagePanel } from './SendMessagePanel'

export function Monitor() {
  const { isConnected, status, currentStatus, screenshots, logs, aiMessages, sendCommand } = useWebSocket()
  const [newContact, setNewContact] = useState('')
  const [interval, setInterval] = useState(0.1)
  const [selectedImage, setSelectedImage] = useState<ScreenshotMessage | null>(null)
  const [filterContact, setFilterContact] = useState<string | null>(null)

  const isRunning =
    currentStatus === 'running' || currentStatus === 'paused' || currentStatus === 'starting'
  const isPaused = currentStatus === 'paused'
  const contacts = status.contacts || []

  // 按联系人过滤截图
  const filteredScreenshots = useMemo(() => {
    if (!filterContact) return screenshots
    return screenshots.filter((s) => s.compare_result.contact === filterContact)
  }, [screenshots, filterContact])

  // 按联系人分组截图
  const screenshotsByContact = useMemo(() => {
    const grouped: Record<string, ScreenshotMessage[]> = {}
    screenshots.forEach((s) => {
      const contact = s.compare_result.contact || 'unknown'
      if (!grouped[contact]) grouped[contact] = []
      grouped[contact].push(s)
    })
    return grouped
  }, [screenshots])

  const handleStart = () => {
    sendCommand('start', { interval })
  }

  const handleStop = () => {
    sendCommand('stop')
  }

  const handleReset = () => {
    sendCommand('reset')
  }

  const handleAddContact = () => {
    if (newContact.trim()) {
      sendCommand('add_contact', { name: newContact.trim() })
      setNewContact('')
    }
  }

  const handleRemoveContact = (name: string) => {
    sendCommand('remove_contact', { name })
  }

  const handleListWindows = () => {
    sendCommand('list_wechat_windows')
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <h1 style={styles.title}>WxEye - WeChat Monitor</h1>
        <div style={styles.connectionStatus}>
          <span
            style={{
              ...styles.statusDot,
              backgroundColor: isConnected ? '#4caf50' : '#f44336',
            }}
          />
          {isConnected ? '已连接' : '未连接'}
        </div>
      </header>

      {/* Contact Management */}
      <div style={styles.contactSection}>
        <div style={styles.contactHeader}>
          <h3 style={styles.contactTitle}>监控联系人 ({contacts.length})</h3>
          <button onClick={handleListWindows} style={styles.discoverButton}>
            发现窗口
          </button>
        </div>

        <div style={styles.addContactRow}>
          <input
            type="text"
            placeholder="输入联系人名称（窗口标题）"
            value={newContact}
            onChange={(e) => setNewContact(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddContact()}
            style={styles.contactInput}
          />
          <button onClick={handleAddContact} style={styles.addButton}>
            添加
          </button>
        </div>

        <div style={styles.contactList}>
          {contacts.length === 0 ? (
            <div style={styles.noContacts}>请先添加要监控的联系人（微信独立聊天窗口的标题）</div>
          ) : (
            contacts.map((contact: ContactStatus) => (
              <div key={contact.name} style={styles.contactItem}>
                <div style={styles.contactInfo}>
                  <span
                    style={{
                      ...styles.visibilityDot,
                      backgroundColor: contact.is_visible ? '#4caf50' : '#666',
                    }}
                  />
                  <span style={styles.contactName}>{contact.name}</span>
                  <span style={styles.contactStats}>
                    ({contact.significant_captures} / {contact.total_captures})
                  </span>
                </div>
                <button
                  onClick={() => handleRemoveContact(contact.name)}
                  style={styles.removeButton}
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Controls */}
      <div style={styles.controls}>
        <div style={styles.inputGroup}>
          <label style={styles.label}>截图间隔 (秒):</label>
          <input
            type="number"
            value={interval}
            onChange={(e) => setInterval(parseFloat(e.target.value))}
            disabled={isRunning}
            min={0.05}
            max={5}
            step={0.05}
            style={styles.input}
          />
        </div>

        <div style={styles.buttonGroup}>
          {!isRunning ? (
            <button
              onClick={handleStart}
              style={styles.startButton}
              disabled={contacts.length === 0}
            >
              开始监控
            </button>
          ) : (
            <button onClick={handleStop} style={styles.stopButton}>
              停止监控
            </button>
          )}
          <button onClick={handleReset} style={styles.resetButton}>
            重置计数
          </button>
        </div>

        <div style={styles.statusInfo}>
          <span
            style={{
              ...styles.statusBadge,
              backgroundColor: isPaused ? '#ff9800' : isRunning ? '#4caf50' : '#666',
            }}
          >
            {isPaused ? '已暂停' : isRunning ? '运行中' : '已停止'}
          </span>
          <span style={styles.statsText}>
            总截图: {status.total_captures ?? 0} | 有效: {status.significant_captures ?? 0}
          </span>
        </div>
      </div>

      {/* Filter tabs */}
      {screenshots.length > 0 && (
        <div style={styles.filterTabs}>
          <button
            onClick={() => setFilterContact(null)}
            style={{
              ...styles.filterTab,
              ...(filterContact === null ? styles.filterTabActive : {}),
            }}
          >
            全部 ({screenshots.length})
          </button>
          {Object.entries(screenshotsByContact).map(([contact, shots]) => (
            <button
              key={contact}
              onClick={() => setFilterContact(contact)}
              style={{
                ...styles.filterTab,
                ...(filterContact === contact ? styles.filterTabActive : {}),
              }}
            >
              {contact} ({shots.length})
            </button>
          ))}
        </div>
      )}

      {/* Main Content */}
      <div style={styles.mainContent}>
        {/* Screenshots Grid */}
        <div style={styles.screenshotsSection}>
          <h2 style={styles.sectionTitle}>
            截图 {filterContact ? `- ${filterContact}` : ''} ({filteredScreenshots.length})
          </h2>
          <div style={styles.screenshotsGrid}>
            {filteredScreenshots.length === 0 ? (
              <div style={styles.placeholder}>暂无截图</div>
            ) : (
              filteredScreenshots.map((screenshot, index) => (
                <div
                  key={screenshot.timestamp + index}
                  style={styles.screenshotItem}
                  onClick={() => setSelectedImage(screenshot)}
                >
                  <div style={styles.contactBadge}>
                    {screenshot.compare_result.contact || 'unknown'}
                  </div>
                  <img
                    src={screenshot.image_data}
                    alt={`Screenshot ${index + 1}`}
                    style={styles.thumbnail}
                  />
                  <div style={styles.screenshotInfo}>
                    <span style={styles.screenshotTime}>
                      {new Date(screenshot.timestamp).toLocaleTimeString()}
                    </span>
                    <span style={styles.screenshotDesc}>
                      {screenshot.compare_result.description}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* AI Message Panel */}
        <div style={styles.aiSection}>
          <AIMessagePanel aiMessages={aiMessages} />
        </div>

        {/* Right Sidebar */}
        <div style={styles.rightSidebar}>
          {/* Send Message Panel */}
          <div style={styles.sendSection}>
            <SendMessagePanel contacts={contacts.map((c: ContactStatus) => c.name)} />
          </div>

          {/* Log Panel */}
          <div style={styles.logSection}>
            <LogPanel logs={logs} />
          </div>
        </div>
      </div>

      {/* Image Viewer Modal */}
      {selectedImage && (
        <ImageViewer image={selectedImage} onClose={() => setSelectedImage(null)} />
      )}
    </div>
  )
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#1a1a2e',
    color: '#eee',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 24px',
    backgroundColor: '#16213e',
    borderBottom: '1px solid #0f3460',
  },
  title: {
    margin: 0,
    fontSize: '22px',
    fontWeight: 600,
  },
  connectionStatus: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '14px',
  },
  statusDot: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
  },
  contactSection: {
    padding: '16px 24px',
    backgroundColor: '#16213e',
    borderBottom: '1px solid #0f3460',
  },
  contactHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '12px',
  },
  contactTitle: {
    margin: 0,
    fontSize: '16px',
    fontWeight: 600,
  },
  discoverButton: {
    padding: '6px 12px',
    fontSize: '12px',
    backgroundColor: '#0f3460',
    color: '#aaa',
    border: '1px solid #1a4b8c',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  addContactRow: {
    display: 'flex',
    gap: '8px',
    marginBottom: '12px',
  },
  contactInput: {
    flex: 1,
    padding: '8px 12px',
    fontSize: '14px',
    backgroundColor: '#0f3460',
    border: '1px solid #1a4b8c',
    borderRadius: '4px',
    color: '#fff',
  },
  addButton: {
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: 600,
    backgroundColor: '#4caf50',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  contactList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
  },
  noContacts: {
    color: '#666',
    fontSize: '14px',
    padding: '8px 0',
  },
  contactItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '6px 12px',
    backgroundColor: '#0f3460',
    borderRadius: '16px',
  },
  contactInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  visibilityDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
  },
  contactName: {
    fontSize: '14px',
  },
  contactStats: {
    fontSize: '12px',
    color: '#888',
  },
  removeButton: {
    background: 'none',
    border: 'none',
    color: '#888',
    fontSize: '18px',
    cursor: 'pointer',
    padding: '0 4px',
    lineHeight: 1,
  },
  controls: {
    display: 'flex',
    alignItems: 'center',
    gap: '24px',
    padding: '12px 24px',
    backgroundColor: '#0f3460',
    flexWrap: 'wrap',
  },
  inputGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  label: {
    fontSize: '14px',
    color: '#aaa',
  },
  input: {
    padding: '8px 12px',
    fontSize: '14px',
    backgroundColor: '#16213e',
    border: '1px solid #1a4b8c',
    borderRadius: '4px',
    color: '#fff',
    width: '80px',
  },
  buttonGroup: {
    display: 'flex',
    gap: '12px',
  },
  startButton: {
    padding: '10px 24px',
    fontSize: '14px',
    fontWeight: 600,
    backgroundColor: '#4caf50',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  stopButton: {
    padding: '10px 24px',
    fontSize: '14px',
    fontWeight: 600,
    backgroundColor: '#f44336',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  resetButton: {
    padding: '10px 24px',
    fontSize: '14px',
    fontWeight: 600,
    backgroundColor: '#ff9800',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  statusInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    marginLeft: 'auto',
  },
  statusBadge: {
    padding: '4px 12px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: 600,
  },
  statsText: {
    fontSize: '14px',
    color: '#aaa',
  },
  filterTabs: {
    display: 'flex',
    gap: '4px',
    padding: '8px 24px',
    backgroundColor: '#16213e',
    borderBottom: '1px solid #0f3460',
    overflowX: 'auto',
  },
  filterTab: {
    padding: '6px 16px',
    fontSize: '13px',
    backgroundColor: '#0f3460',
    color: '#aaa',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  filterTabActive: {
    backgroundColor: '#1a4b8c',
    color: '#fff',
  },
  mainContent: {
    display: 'grid',
    gridTemplateColumns: '1fr 400px 320px',
    gap: '16px',
    padding: '16px 24px',
    minHeight: 'calc(100vh - 280px)',
  },
  rightSidebar: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  sendSection: {
    backgroundColor: '#16213e',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  screenshotsSection: {
    backgroundColor: '#16213e',
    borderRadius: '8px',
    padding: '16px',
    overflow: 'hidden',
  },
  sectionTitle: {
    margin: '0 0 16px 0',
    fontSize: '18px',
    fontWeight: 600,
  },
  screenshotsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gap: '12px',
    maxHeight: 'calc(100vh - 380px)',
    overflowY: 'auto',
  },
  placeholder: {
    gridColumn: '1 / -1',
    textAlign: 'center',
    padding: '48px',
    color: '#666',
  },
  screenshotItem: {
    backgroundColor: '#0f3460',
    borderRadius: '8px',
    overflow: 'hidden',
    cursor: 'pointer',
    transition: 'transform 0.2s',
    position: 'relative',
  },
  contactBadge: {
    position: 'absolute',
    top: '8px',
    left: '8px',
    padding: '2px 8px',
    backgroundColor: 'rgba(0,0,0,0.7)',
    borderRadius: '4px',
    fontSize: '11px',
    color: '#fff',
    zIndex: 1,
  },
  thumbnail: {
    width: '100%',
    height: '120px',
    objectFit: 'cover',
  },
  screenshotInfo: {
    padding: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  screenshotTime: {
    fontSize: '11px',
    color: '#888',
  },
  screenshotDesc: {
    fontSize: '11px',
    color: '#aaa',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  aiSection: {
    backgroundColor: '#16213e',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  logSection: {
    backgroundColor: '#16213e',
    borderRadius: '8px',
    overflow: 'hidden',
    flex: 1,
    minHeight: '200px',
  },
}
