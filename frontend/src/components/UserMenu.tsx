import { useEffect, useRef, useState } from 'react'
import './UserMenu.css'

interface Props {
  label: string
  imageUrl?: string | null
  onOpenSettings: () => void
  onLogout: () => void
  badgeCount?: number
  badgeTitle?: string
}

function getInitials(label: string): string {
  const trimmed = label.trim()
  if (!trimmed) return '?'
  const parts = trimmed.split(/\s+/).filter(Boolean)
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase()
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function UserMenu({
  label,
  imageUrl,
  onOpenSettings,
  onLogout,
  badgeCount = 0,
  badgeTitle,
}: Props) {
  const [open, setOpen] = useState(false)
  const [imageFailed, setImageFailed] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setImageFailed(false)
  }, [imageUrl])

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    const keyHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    document.addEventListener('keydown', keyHandler)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('keydown', keyHandler)
    }
  }, [open])

  return (
    <div className="user-menu" ref={wrapRef}>
      <button
        className="user-menu-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="user-menu-avatar" aria-hidden="true">
          {imageUrl && !imageFailed ? (
            <img
              src={imageUrl}
              alt=""
              onError={() => setImageFailed(true)}
            />
          ) : (
            <span className="user-menu-avatar-initials">
              {getInitials(label)}
            </span>
          )}
        </span>
        <span className="user-menu-label">{label}</span>
        {badgeCount > 0 && (
          <span
            className="user-menu-badge"
            title={badgeTitle ?? `${badgeCount} pending`}
            aria-label={badgeTitle ?? `${badgeCount} pending`}
          >
            {badgeCount > 99 ? '99+' : badgeCount}
          </span>
        )}
        <span className="user-menu-caret" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="user-menu-dropdown" role="menu">
          <button
            role="menuitem"
            className="user-menu-item"
            onClick={() => {
              setOpen(false)
              onOpenSettings()
            }}
          >
            Settings
            {badgeCount > 0 && (
              <span
                className="user-menu-item-badge"
                title={badgeTitle ?? `${badgeCount} pending`}
              >
                {badgeCount > 99 ? '99+' : badgeCount}
              </span>
            )}
          </button>
          <button
            role="menuitem"
            className="user-menu-item"
            onClick={() => {
              setOpen(false)
              onLogout()
            }}
          >
            Logout
          </button>
        </div>
      )}
    </div>
  )
}

export default UserMenu
