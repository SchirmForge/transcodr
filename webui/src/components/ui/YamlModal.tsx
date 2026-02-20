import { useEffect } from 'react'

interface YamlModalProps {
  title: string
  content: string
  onClose: () => void
}

export function YamlModal({ title, content, onClose }: YamlModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-gray-900 rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{title}</span>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-lg leading-none"
            title="Close"
          >
            ✕
          </button>
        </div>
        <div className="overflow-auto flex-1 p-4">
          <pre className="text-xs font-mono text-gray-800 dark:text-gray-200 whitespace-pre select-text">
            {content}
          </pre>
        </div>
      </div>
    </div>
  )
}
