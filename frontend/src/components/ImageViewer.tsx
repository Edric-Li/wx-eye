import React from 'react'
import { ScreenshotMessage } from '../hooks/useWebSocket'

interface ImageViewerProps {
  image: ScreenshotMessage
  onClose: () => void
}

export function ImageViewer({ image, onClose }: ImageViewerProps) {
  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h3 style={styles.title}>截图详情</h3>
          <button style={styles.closeButton} onClick={onClose}>
            ✕
          </button>
        </div>

        <div style={styles.content}>
          <img src={image.image_data} alt="Screenshot" style={styles.image} />

          <div style={styles.info}>
            {image.compare_result.contact && (
              <div style={styles.infoRow}>
                <span style={styles.infoLabel}>联系人:</span>
                <span style={{ ...styles.infoValue, color: '#4caf50', fontWeight: 600 }}>
                  {image.compare_result.contact}
                </span>
              </div>
            )}
            <div style={styles.infoRow}>
              <span style={styles.infoLabel}>时间:</span>
              <span style={styles.infoValue}>{new Date(image.timestamp).toLocaleString()}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.infoLabel}>变化级别:</span>
              <span
                style={{
                  ...styles.infoValue,
                  color: image.compare_result.level === 'different' ? '#4caf50' : '#ff9800',
                }}
              >
                {image.compare_result.level}
              </span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.infoLabel}>哈希距离:</span>
              <span style={styles.infoValue}>{image.compare_result.hash_distance}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.infoLabel}>描述:</span>
              <span style={styles.infoValue}>{image.compare_result.description}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.infoLabel}>文件:</span>
              <span style={styles.infoValue}>{image.filename}</span>
            </div>
          </div>
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
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    backgroundColor: '#16213e',
    borderRadius: '8px',
    maxWidth: '90vw',
    maxHeight: '90vh',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
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
  closeButton: {
    background: 'none',
    border: 'none',
    color: '#888',
    fontSize: '20px',
    cursor: 'pointer',
    padding: '4px 8px',
  },
  content: {
    padding: '16px',
    overflow: 'auto',
  },
  image: {
    maxWidth: '100%',
    maxHeight: '60vh',
    objectFit: 'contain',
    borderRadius: '4px',
  },
  info: {
    marginTop: '16px',
    padding: '16px',
    backgroundColor: '#0f3460',
    borderRadius: '4px',
  },
  infoRow: {
    display: 'flex',
    marginBottom: '8px',
  },
  infoLabel: {
    width: '100px',
    color: '#888',
    fontSize: '14px',
  },
  infoValue: {
    fontSize: '14px',
    color: '#eee',
  },
}
