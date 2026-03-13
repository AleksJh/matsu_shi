import { useState } from 'react'
import { createPortal } from 'react-dom'

interface ImageViewerProps {
  url: string
  alt?: string
}

export function ImageViewer({ url, alt = 'Изображение' }: ImageViewerProps) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <img
        src={url}
        alt={alt}
        className="mt-2 h-24 w-24 cursor-pointer rounded object-cover"
        onClick={() => setOpen(true)}
      />
      {open &&
        createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
            onClick={() => setOpen(false)}
            role="dialog"
            aria-modal="true"
            aria-label="Просмотр изображения"
          >
            <img
              src={url}
              alt={alt}
              className="max-h-full max-w-full object-contain"
              onClick={(e) => e.stopPropagation()}
            />
          </div>,
          document.body,
        )}
    </>
  )
}
