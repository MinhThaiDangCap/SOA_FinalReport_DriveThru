import { useEffect, useRef, useState } from 'react'

import Icon from './Icon.jsx'

function timeAgo(date) {
  const min = Math.floor((Date.now() - date.getTime()) / 60000)
  if (min < 1) return 'vừa xong'
  if (min < 60) return `${min} phút trước`
  return date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Nút chuông + danh sách thông báo của màn hình quầy.
 * items: [{ key, type: 'arrived' | 'new', title, detail, at: Date, read }]
 * Bấm một thông báo -> onPick(item) (vd. cuộn tới thẻ đơn); onReadAll / onClear để dọn.
 */
export default function NotificationBell({ items, onPick, onReadAll, onClear }) {
  const [open, setOpen] = useState(false)
  const wrap = useRef(null)
  const unread = items.filter((i) => !i.read)
  const urgent = unread.some((i) => i.type === 'arrived')

  // Bấm ra ngoài hoặc Esc thì đóng
  useEffect(() => {
    if (!open) return undefined
    function onDown(e) {
      if (wrap.current && !wrap.current.contains(e.target)) setOpen(false)
    }
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div className="bell-wrap" ref={wrap}>
      <button
        type="button"
        className={`bell-btn${unread.length ? ' bell-unread' : ''}${urgent ? ' bell-urgent' : ''}`}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={`Thông báo${unread.length ? `, ${unread.length} chưa đọc` : ''}`}
      >
        <Icon name="bell" size={20} />
        <span className="bell-label">Thông báo</span>
        {unread.length > 0 && <span className="bell-count">{unread.length}</span>}
      </button>

      {open && (
        <div className="bell-panel" role="dialog" aria-label="Danh sách thông báo">
          <div className="bell-panel-head">
            <strong>Thông báo</strong>
            <div className="bell-panel-actions">
              {unread.length > 0 && (
                <button type="button" className="link-btn" onClick={onReadAll}>
                  Đánh dấu đã đọc
                </button>
              )}
              {items.length > 0 && (
                <button type="button" className="link-btn" onClick={onClear}>
                  Xóa hết
                </button>
              )}
            </div>
          </div>

          {items.length === 0 ? (
            <p className="bell-empty">Chưa có thông báo nào.</p>
          ) : (
            <ul className="bell-list">
              {items.map((n) => (
                <li key={n.key}>
                  <button
                    type="button"
                    className={`bell-item bell-${n.type}${n.read ? '' : ' bell-item-unread'}`}
                    onClick={() => {
                      onPick(n)
                      setOpen(false)
                    }}
                  >
                    <span className="bell-item-icon">
                      <Icon name={n.type === 'arrived' ? 'car' : 'utensils'} size={18} />
                    </span>
                    <span className="bell-item-text">
                      <strong>{n.title}</strong>
                      <small>
                        {n.detail} · {timeAgo(n.at)}
                      </small>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
