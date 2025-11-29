import React, { useState } from 'react'

const API_BASE = 'http://localhost:8000'

interface SendResult {
  success: boolean
  message: string
  elapsed_ms: number
  error?: string
  contact?: string
}

interface SendMessagePanelProps {
  contacts: string[]
}

export function SendMessagePanel({ contacts }: SendMessagePanelProps) {
  const [message, setMessage] = useState('')
  const [selectedContact, setSelectedContact] = useState<string>('')
  const [sending, setSending] = useState(false)
  const [lastResult, setLastResult] = useState<SendResult | null>(null)

  const handleSend = async () => {
    if (!message.trim()) {
      setLastResult({ success: false, message: '请输入消息内容', elapsed_ms: 0 })
      return
    }

    if (!selectedContact) {
      setLastResult({ success: false, message: '请选择联系人', elapsed_ms: 0 })
      return
    }

    setSending(true)
    setLastResult(null)

    try {
      const params = new URLSearchParams({
        text: message,
        contact: selectedContact,
      })
      const res = await fetch(`${API_BASE}/api/message/send?${params}`, {
        method: 'POST',
      })
      const data: SendResult = await res.json()
      setLastResult(data)
      if (data.success) {
        setMessage('')
      }
    } catch (err) {
      setLastResult({ success: false, message: `发送失败: ${err}`, elapsed_ms: 0 })
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={styles.container}>
      <h3 style={styles.title}>发送消息</h3>

      {/* 联系人选择 */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>选择联系人</div>
        {contacts.length === 0 ? (
          <div style={styles.noContacts}>请先添加监控联系人</div>
        ) : (
          <select
            value={selectedContact}
            onChange={(e) => setSelectedContact(e.target.value)}
            style={styles.select}
          >
            <option value="">-- 选择联系人 --</option>
            {contacts.map((contact) => (
              <option key={contact} value={contact}>
                {contact}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* 消息发送 */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>消息内容</div>
        <textarea
          placeholder="输入要发送的消息..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          style={styles.messageInput}
          rows={3}
        />
        <button
          onClick={handleSend}
          disabled={sending || !message.trim() || !selectedContact}
          style={{
            ...styles.sendButton,
            opacity: sending || !message.trim() || !selectedContact ? 0.5 : 1,
          }}
        >
          {sending ? '发送中...' : '发送 (Enter)'}
        </button>
      </div>

      {/* 结果显示 */}
      {lastResult && (
        <div
          style={{
            ...styles.result,
            backgroundColor: lastResult.success ? '#1b4332' : '#4a1515',
            borderColor: lastResult.success ? '#2d6a4f' : '#7a2020',
          }}
        >
          <div style={styles.resultStatus}>
            {lastResult.success ? '✓ 成功' : '✗ 失败'}
          </div>
          <div style={styles.resultMessage}>{lastResult.message}</div>
          {lastResult.elapsed_ms > 0 && (
            <div style={styles.resultTime}>耗时: {lastResult.elapsed_ms}ms</div>
          )}
        </div>
      )}
    </div>
  )
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    padding: '16px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  title: {
    margin: 0,
    fontSize: '16px',
    fontWeight: 600,
    color: '#fff',
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  sectionTitle: {
    fontSize: '13px',
    color: '#aaa',
    fontWeight: 500,
  },
  select: {
    padding: '10px',
    fontSize: '14px',
    backgroundColor: '#0f3460',
    border: '1px solid #1a4b8c',
    borderRadius: '4px',
    color: '#fff',
    cursor: 'pointer',
  },
  noContacts: {
    fontSize: '13px',
    color: '#666',
    padding: '8px 0',
  },
  messageInput: {
    padding: '10px',
    fontSize: '14px',
    backgroundColor: '#0f3460',
    border: '1px solid #1a4b8c',
    borderRadius: '4px',
    color: '#fff',
    resize: 'vertical',
    fontFamily: 'inherit',
  },
  sendButton: {
    padding: '10px 16px',
    fontSize: '14px',
    fontWeight: 600,
    backgroundColor: '#4caf50',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  result: {
    padding: '12px',
    borderRadius: '4px',
    border: '1px solid',
  },
  resultStatus: {
    fontSize: '14px',
    fontWeight: 600,
    marginBottom: '4px',
  },
  resultMessage: {
    fontSize: '13px',
    color: '#ccc',
  },
  resultTime: {
    fontSize: '11px',
    color: '#888',
    marginTop: '4px',
  },
}
