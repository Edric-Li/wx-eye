import React, { useMemo, useRef, useEffect } from 'react'
import { AIMessage } from '../hooks/useWebSocket'

interface AIMessagePanelProps {
  aiMessages: AIMessage[]
}

interface ChatItem {
  sender: string
  content: string
  contact: string
  timestamp: string
}

export function AIMessagePanel({ aiMessages }: AIMessagePanelProps) {
  const listRef = useRef<HTMLDivElement>(null)

  // 把所有消息合并成一个聊天记录列表，按时间顺序（旧的在上，新的在下）
  const allMessages = useMemo(() => {
    const messages: ChatItem[] = []

    // 倒序遍历（aiMessages 是新的在前），这样最终结果是旧的在上
    for (let i = aiMessages.length - 1; i >= 0; i--) {
      const msg = aiMessages[i]
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
  }, [aiMessages])

  // 新消息时自动滚动到底部
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [allMessages.length])

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h3 style={styles.title}>AI 消息识别</h3>
        <span style={styles.count}>{allMessages.length}</span>
      </div>

      <div style={styles.chatContainer} ref={listRef}>
        {allMessages.length === 0 ? (
          <div style={styles.placeholder}>
            <div style={styles.placeholderIcon}>🤖</div>
            <div>等待 AI 识别新消息...</div>
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
                {isMe && <div style={{...styles.avatar, ...styles.myAvatar}}>我</div>}
              </div>
            )
          })
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
    width: '32px',
    height: '32px',
    borderRadius: '4px',
    backgroundColor: '#1a4b8c',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '12px',
    fontWeight: 600,
    color: '#fff',
    flexShrink: 0,
  },
  myAvatar: {
    backgroundColor: '#1a5f4a',
  },
  bubble: {
    maxWidth: '70%',
    padding: '8px 12px',
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
}
