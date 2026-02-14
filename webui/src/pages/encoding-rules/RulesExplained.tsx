
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import encodingRulesDoc from '../../content/encoding-rules.md?raw'

export function RulesExplained() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Encoding Rules Explained</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">
        Quick orientation for profiles and watch folders.
      </p>

      <div className="markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{encodingRulesDoc}</ReactMarkdown>
      </div>
    </div>
  )
}
