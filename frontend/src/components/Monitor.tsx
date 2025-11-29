import React, { useState, useMemo } from 'react'
import { useWebSocket, ScreenshotMessage, ContactStatus } from '../hooks/useWebSocket'
import { ImageViewer } from './ImageViewer'
import { ChatPanel } from './ChatPanel'
import { LogModal } from './LogModal'
import { WindowDiscoverModal } from './WindowDiscoverModal'

export function Monitor() {
  const {
    isConnected,
    status,
    currentStatus,
    screenshots,
    rawLogs,
    aiMessages,
    sendCommand,
    subscribeRawLogs,
    unsubscribeRawLogs,
  } = useWebSocket()
  const [newContact, setNewContact] = useState('')
  const [selectedImage, setSelectedImage] = useState<ScreenshotMessage | null>(null)
  const [selectedContact, setSelectedContact] = useState<string | null>(null)
  const [showLogModal, setShowLogModal] = useState(false)
  const [showWindowModal, setShowWindowModal] = useState(false)

  const isRunning =
    currentStatus === 'running' || currentStatus === 'paused' || currentStatus === 'starting'
  const isPaused = currentStatus === 'paused'
  const contacts = status.contacts || []

  // 过滤当前选中联系人的截图
  const filteredScreenshots = useMemo(() => {
    if (!selectedContact) return screenshots.slice(0, 20)
    return screenshots
      .filter((s) => s.compare_result.contact === selectedContact)
      .slice(0, 20)
  }, [screenshots, selectedContact])

  const handleStart = () => {
    sendCommand('start')
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
    if (selectedContact === name) {
      setSelectedContact(null)
    }
  }

  const handleSelectContact = (name: string) => {
    setSelectedContact(selectedContact === name ? null : name)
  }

  const handleAddContactFromWindow = (name: string) => {
    sendCommand('add_contact', { name })
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <h1 style={styles.title}>WxEye - WeChat Monitor</h1>
        <div style={styles.headerRight}>
          <button onClick={() => setShowWindowModal(true)} style={styles.headerButton}>
            发现窗口
          </button>
          <button onClick={() => setShowLogModal(true)} style={styles.headerButton}>
            日志
          </button>
          <div style={styles.connectionStatus}>
            <span
              style={{
                ...styles.statusDot,
                backgroundColor: isConnected ? '#4caf50' : '#f44336',
              }}
            />
            {isConnected ? '已连接' : '未连接'}
          </div>
        </div>
      </header>

      {/* Contact Management */}
      <div style={styles.contactSection}>
        <div style={styles.contactHeader}>
          <h3 style={styles.contactTitle}>监控联系人 ({contacts.length})</h3>
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
              <div
                key={contact.name}
                style={{
                  ...styles.contactItem,
                  ...(selectedContact === contact.name ? styles.contactItemSelected : {}),
                }}
                onClick={() => handleSelectContact(contact.name)}
              >
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
                  onClick={(e) => {
                    e.stopPropagation()
                    handleRemoveContact(contact.name)
                  }}
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

      {/* Main Content: Chat + Screenshot */}
      <div style={styles.mainContent}>
        {/* Left: Chat Panel */}
        <div style={styles.chatSection}>
          <ChatPanel aiMessages={aiMessages} selectedContact={selectedContact} />
        </div>

        {/* Right: Screenshot Panel */}
        <div style={styles.screenshotSection}>
          <div style={styles.screenshotHeader}>
            <h3 style={styles.sectionTitle}>
              截图 {selectedContact ? `- ${selectedContact}` : ''}
            </h3>
            <span style={styles.screenshotCount}>{filteredScreenshots.length}</span>
          </div>
          <div style={styles.screenshotList}>
            {filteredScreenshots.length === 0 ? (
              <div style={styles.placeholder}>暂无截图</div>
            ) : (
              filteredScreenshots.map((screenshot, index) => (
                <div
                  key={screenshot.timestamp + index}
                  style={styles.screenshotItem}
                  onClick={() => setSelectedImage(screenshot)}
                >
                  <img
                    src={screenshot.image_data}
                    alt={`Screenshot ${index + 1}`}
                    style={styles.thumbnail}
                  />
                  <div style={styles.screenshotInfo}>
                    <span style={styles.screenshotTime}>
                      {new Date(screenshot.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Image Viewer Modal */}
      {selectedImage && (
        <ImageViewer image={selectedImage} onClose={() => setSelectedImage(null)} />
      )}

      {/* Log Modal */}
      <LogModal
        isOpen={showLogModal}
        onClose={() => setShowLogModal(false)}
        logs={rawLogs}
        onSubscribe={subscribeRawLogs}
        onUnsubscribe={unsubscribeRawLogs}
      />

      {/* Window Discover Modal */}
      <WindowDiscoverModal
        isOpen={showWindowModal}
        onClose={() => setShowWindowModal(false)}
        onAddContact={handleAddContactFromWindow}
      />
    </div>
  )
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#1a1a2e',
    color: '#eee',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    display: 'flex',
    flexDirection: 'column',
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
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  headerButton: {
    padding: '8px 16px',
    fontSize: '13px',
    backgroundColor: '#0f3460',
    color: '#aaa',
    border: '1px solid #1a4b8c',
    borderRadius: '4px',
    cursor: 'pointer',
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
    cursor: 'pointer',
    border: '2px solid transparent',
    transition: 'border-color 0.2s',
  },
  contactItemSelected: {
    borderColor: '#4caf50',
    backgroundColor: '#1a4b8c',
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
  mainContent: {
    display: 'flex',
    flex: 1,
    gap: '16px',
    padding: '16px 24px',
    minHeight: 0,
  },
  chatSection: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
  },
  screenshotSection: {
    width: '300px',
    flexShrink: 0,
    backgroundColor: '#16213e',
    borderRadius: '8px',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  screenshotHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    borderBottom: '1px solid #0f3460',
  },
  sectionTitle: {
    margin: 0,
    fontSize: '14px',
    fontWeight: 600,
  },
  screenshotCount: {
    backgroundColor: '#0f3460',
    padding: '2px 10px',
    borderRadius: '10px',
    fontSize: '12px',
  },
  screenshotList: {
    flex: 1,
    overflowY: 'auto',
    padding: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  placeholder: {
    textAlign: 'center',
    padding: '24px',
    color: '#666',
  },
  screenshotItem: {
    backgroundColor: '#0f3460',
    borderRadius: '4px',
    overflow: 'hidden',
    cursor: 'pointer',
    transition: 'transform 0.2s',
  },
  thumbnail: {
    width: '100%',
    height: '160px',
    objectFit: 'cover',
  },
  screenshotInfo: {
    padding: '6px 8px',
  },
  screenshotTime: {
    fontSize: '11px',
    color: '#888',
  },
}
