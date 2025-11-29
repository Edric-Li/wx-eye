import React, { useMemo, useRef, useEffect, useState } from 'react'
import { AIMessage } from '../hooks/useWebSocket'

interface ChatPanelProps {
  aiMessages: AIMessage[]
  selectedContact: string | null
}

interface ChatItem {
  sender: string
  content: string
  contact: string
  timestamp: string
}

export function ChatPanel({ aiMessages, selectedContact }: ChatPanelProps) {
  const listRef = useRef<HTMLDivElement>(null)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)

  // 过滤当前选中联系人的消息，并合并成聊天记录列表
  const allMessages = useMemo(() => {
    const messages: ChatItem[] = []

    // 过滤当前联系人的消息
    const filtered = selectedContact
      ? aiMessages.filter((m) => m.contact === selectedContact)
      : aiMessages

    // 倒序遍历（aiMessages 是新的在前），这样最终结果是旧的在上
    for (let i = filtered.length - 1; i >= 0; i--) {
      const msg = filtered[i]
      for (const chatMsg of msg.new_messages) {
        messages.push({
          sender: chatMsg.sender || '对方',
          content: chatMsg.content,
          contact: msg.contact,
          timestamp: msg.timestamp,
        })
      }
    }

    return messages
  }, [aiMessages, selectedContact])

  // 新消息时自动滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [allMessages.length])

  const handleSend = async () => {
    if (!message.trim() || !selectedContact) return

    setSending(true)
    try {
      const params = new URLSearchParams({
        text: message,
        contact: selectedContact,
      })
      const res = await fetch(`/api/message/send?${params}`, {
        method: 'POST',
      })
      const data = await res.json()
      if (data.success) {
        setMessage('')
      }
    } catch (err) {
      console.error('发送失败:', err)
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
      {/* Header */}
      <div style={styles.header}>
        <h3 style={styles.title}>
          {selectedContact ? selectedContact : '聊天记录'}
        </h3>
        <span style={styles.count}>{allMessages.length}</span>
      </div>

      {/* Chat messages */}
      <div style={styles.chatContainer} ref={listRef}>
        {!selectedContact ? (
          <div style={styles.placeholder}>
            <div style={styles.placeholderIcon}>👈</div>
            <div>请先选择一个联系人</div>
          </div>
        ) : allMessages.length === 0 ? (
          <div style={styles.placeholder}>
            <div style={styles.placeholderIcon}>💬</div>
            <div>等待消息...</div>
          </div>
        ) : (
          allMessages.map((msg, index) => {
            const isMe = msg.sender === '我'
            return (
              <div
                key={index}
                style={{
                  ...styles.messageRow,
                  justifyContent: isMe ? 'flex-end' : 'flex-start',
                }}
              >
                {!isMe && <div style={styles.avatar}>{msg.sender[0]}</div>}
                <div
                  style={{
                    ...styles.bubble,
                    ...(isMe ? styles.myBubble : styles.otherBubble),
                  }}
                >
                  {!isMe && <div style={styles.senderName}>{msg.sender}</div>}
                  <div style={styles.content}>{msg.content}</div>
                </div>
                {isMe && <div style={{ ...styles.avatar, ...styles.myAvatar }}>我</div>}
              </div>
            )
          })
        )}
      </div>

      {/* Input area */}
      <div style={styles.inputArea}>
        <textarea
          placeholder={selectedContact ? '输入消息...' : '请先选择联系人'}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!selectedContact || sending}
          style={{
            ...styles.input,
            opacity: !selectedContact ? 0.5 : 1,
          }}
          rows={2}
        />
        <button
          onClick={handleSend}
          disabled={!selectedContact || !message.trim() || sending}
          style={{
            ...styles.sendButton,
            opacity: !selectedContact || !message.trim() || sending ? 0.5 : 1,
          }}
        >
          {sending ? '...' : '发送'}
        </button>
      </div>
    </div>
  )
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    backgroundColor: '#16213e',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 16px',
    borderBottom: '1px solid #0f3460',
    flexShrink: 0,
  },
  title: {
    margin: 0,
    fontSize: '16px',
    fontWeight: 600,
  },
  count: {
    backgroundColor: '#00bfa5',
    padding: '2px 10px',
    borderRadius: '10px',
    fontSize: '12px',
  },
  chatContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    backgroundColor: '#ebebeb',
  },
  placeholder: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#666',
  },
  placeholderIcon: {
    fontSize: '40px',
    marginBottom: '12px',
  },
  messageRow: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
  },
  avatar: {
    width: '36px',
    height: '36px',
    borderRadius: '4px',
    backgroundColor: '#1a4b8c',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
    fontWeight: 600,
    color: '#fff',
    flexShrink: 0,
  },
  myAvatar: {
    backgroundColor: '#1a5f4a',
  },
  bubble: {
    maxWidth: '70%',
    padding: '10px 12px',
    borderRadius: '4px',
    wordBreak: 'break-word',
  },
  otherBubble: {
    backgroundColor: '#fff',
    color: '#000',
    borderTopLeftRadius: 0,
  },
  myBubble: {
    backgroundColor: '#95ec69',
    color: '#000',
    borderTopRightRadius: 0,
  },
  senderName: {
    fontSize: '11px',
    color: '#666',
    marginBottom: '2px',
  },
  content: {
    fontSize: '14px',
    lineHeight: 1.4,
  },
  inputArea: {
    display: 'flex',
    gap: '8px',
    padding: '12px',
    borderTop: '1px solid #0f3460',
    backgroundColor: '#16213e',
  },
  input: {
    flex: 1,
    padding: '10px',
    fontSize: '14px',
    backgroundColor: '#0f3460',
    border: '1px solid #1a4b8c',
    borderRadius: '4px',
    color: '#fff',
    resize: 'none',
    fontFamily: 'inherit',
  },
  sendButton: {
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: 600,
    backgroundColor: '#07c160',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    alignSelf: 'flex-end',
  },
}
