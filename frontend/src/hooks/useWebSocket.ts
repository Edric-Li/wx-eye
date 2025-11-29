import { useState, useEffect, useCallback, useRef } from 'react'

export interface ScreenshotMessage {
  type: 'screenshot'
  timestamp: string
  filename: string
  is_significant: boolean
  image_data: string
  compare_result: {
    level: string
    hash_distance: number
    description: string
    is_first: boolean
    contact?: string // 联系人名称
  }
}

export interface LogMessage {
  type: 'log'
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
  extra: Record<string, unknown>
}

export interface AIMessageItem {
  sender: string
  content: string
  time?: string
}

export interface AIMessage {
  type: 'ai_message'
  timestamp: string
  contact: string
  new_messages: AIMessageItem[]
  summary: string
  message_count: number
  processing_stats: {
    ocr_time_ms?: number
    ai_time_ms?: number
    tokens_used?: number
    stage?: string
  }
}

export interface ContactStatus {
  name: string
  is_visible: boolean
  total_captures: number
  significant_captures: number
}

export interface StatusMessage {
  type: 'status'
  timestamp: string
  status: string // 'running' | 'paused' | 'stopped' | 'starting' | 'connected'
  details: {
    is_running?: boolean
    interval?: number
    total_captures?: number
    significant_captures?: number
    message?: string
    contacts?: ContactStatus[]
    visible_contacts?: string[]
    total_contacts?: number
  }
}

export type WSMessage = ScreenshotMessage | LogMessage | StatusMessage | AIMessage

interface UseWebSocketResult {
  isConnected: boolean
  status: StatusMessage['details']
  currentStatus: string
  screenshots: ScreenshotMessage[]
  logs: LogMessage[]
  aiMessages: AIMessage[]
  sendCommand: (command: string, params?: Record<string, unknown>) => void
  connect: () => void
  disconnect: () => void
}

export function useWebSocket(): UseWebSocketResult {
  const [isConnected, setIsConnected] = useState(false)
  const [status, setStatus] = useState<StatusMessage['details']>({})
  const [currentStatus, setCurrentStatus] = useState('stopped')
  const [screenshots, setScreenshots] = useState<ScreenshotMessage[]>([])
  const [logs, setLogs] = useState<LogMessage[]>([])
  const [aiMessages, setAIMessages] = useState<AIMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number>()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('[WS] Connected')
      setIsConnected(true)
      ws.send(JSON.stringify({ command: 'status' }))
    }

    ws.onclose = () => {
      console.log('[WS] Disconnected')
      setIsConnected(false)
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect()
      }, 3000)
    }

    ws.onerror = (error) => {
      console.error('[WS] Error:', error)
    }

    ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data)

        switch (message.type) {
          case 'screenshot':
            setScreenshots((prev) => [message, ...prev].slice(0, 100))
            break

          case 'log':
            setLogs((prev) => [message, ...prev].slice(0, 200))
            break

          case 'status':
            setStatus(message.details)
            setCurrentStatus(message.status)
            break

          case 'ai_message':
            setAIMessages((prev) => [message, ...prev].slice(0, 100))
            break
        }
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    }

    wsRef.current = ws
  }, [])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    wsRef.current?.close()
    wsRef.current = null
    setIsConnected(false)
  }, [])

  const sendCommand = useCallback((command: string, params?: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command, ...params }))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    isConnected,
    status,
    currentStatus,
    screenshots,
    logs,
    aiMessages,
    sendCommand,
    connect,
    disconnect,
  }
}
