interface SortOption {
  value: string
  label: string
}

interface SortSelectProps {
  value: string
  direction: 'asc' | 'desc'
  onValueChange: (value: string) => void
  onDirectionChange: (direction: 'asc' | 'desc') => void
  options: SortOption[]
}

export function SortSelect({
  value,
  direction,
  onValueChange,
  onDirectionChange,
  options,
}: SortSelectProps) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
        Sort:
      </label>
      <select
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className="text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-400"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <button
        onClick={() => onDirectionChange(direction === 'asc' ? 'desc' : 'asc')}
        className="px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-400"
        title={direction === 'asc' ? 'Ascending' : 'Descending'}
      >
        {direction === 'asc' ? '↑' : '↓'}
      </button>
    </div>
  )
}
