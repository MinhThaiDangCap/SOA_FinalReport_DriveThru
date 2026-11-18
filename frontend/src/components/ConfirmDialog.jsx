import { useEffect, useRef } from 'react'

import Icon from './Icon.jsx'

/**
 * Hộp xác nhận thay cho window.confirm: có tiêu đề, nội dung tùy ý, 2 nút.
 * Esc hoặc bấm ra ngoài = hủy. confirmDisabled để chặn nút xác nhận khi chưa đủ điều kiện.
 */
export default function ConfirmDialog({
  title,
  children,
  confirmLabel = 'Xác nhận',
  cancelLabel = 'Quay lại',
  confirmDisabled = false,
  busy = false,
  tone = 'brand',
  onConfirm,
  onCancel,
}) {
  const confirmRef = useRef(null)

  useEffect(() => {
    confirmRef.current?.focus()
    function onKey(e) {
      if (e.key === 'Escape' && !busy) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, onCancel])

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !busy && onCancel()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div className="modal-head">
          <h2 id="modal-title">{title}</h2>
          <button type="button" className="modal-close" onClick={onCancel} disabled={busy}>
            <Icon name="x" size={18} label="Đóng" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            className={`btn${tone === 'success' ? ' btn-success' : ''}`}
            onClick={onConfirm}
            disabled={busy || confirmDisabled}
          >
            {busy ? 'Đang xử lý...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
