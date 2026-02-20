import { useState } from 'react'
import { apiClient } from '../api/client'

interface YamlModalState {
  isOpen: boolean
  isLoading: boolean
  title: string
  content: string | null
  open: (filePath: string, title: string) => Promise<void>
  close: () => void
}

/**
 * Shared hook for displaying a YAML (or any text) file in a modal.
 *
 * Usage:
 *   const yaml = useYamlModal()
 *   <button onClick={() => yaml.open(filePath, 'my-profile.yaml')}>See yaml…</button>
 *   {yaml.isOpen && yaml.content !== null && (
 *     <YamlModal title={yaml.title} content={yaml.content} onClose={yaml.close} />
 *   )}
 */
export function useYamlModal(): YamlModalState {
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState<string | null>(null)

  async function open(filePath: string, modalTitle: string) {
    setTitle(modalTitle)
    if (content === null) {
      setIsLoading(true)
      try {
        const res = await apiClient.get('/config-file', { params: { path: filePath } })
        setContent(res.data.content)
      } catch {
        setContent('# Failed to load file content')
      } finally {
        setIsLoading(false)
      }
    }
    setIsOpen(true)
  }

  function close() {
    setIsOpen(false)
  }

  return { isOpen, isLoading, title, content, open, close }
}
