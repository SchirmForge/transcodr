import { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import logoImg from '../../assets/videoforge-final-alpha.png'

interface NavItem {
  label: string
  to: string
}

interface NavSection {
  id: string
  title: string
  items: NavItem[]
}

const navigation: NavSection[] = [
  {
    id: 'jobs',
    title: 'Jobs',
    items: [
      { label: 'Activity', to: '/jobs/activity' },
      { label: 'History', to: '/jobs/history' },
    ],
  },
  {
    id: 'monitoring',
    title: 'Monitoring',
    items: [
      { label: 'Watch Folders', to: '/watchfolders' },
      { label: 'Profiles', to: '/profiles' },
    ],
  },
  {
    id: 'settings',
    title: 'Settings',
    items: [
      { label: 'General', to: '/settings/general' },
    ],
  },
  {
    id: 'system',
    title: 'System',
    items: [
      { label: 'Status', to: '/system/status' },
    ],
  },
]

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`w-4 h-4 transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  )
}

function findActiveSectionId(pathname: string): string | null {
  for (const section of navigation) {
    if (section.items.some(item => pathname.startsWith(item.to))) {
      return section.id
    }
  }
  return null
}

export function Sidebar() {
  const location = useLocation()
  const [expandedSection, setExpandedSection] = useState<string | null>(null)

  // Auto-expand section based on current route
  useEffect(() => {
    const activeSection = findActiveSectionId(location.pathname)
    if (activeSection) {
      setExpandedSection(activeSection)
    }
  }, [location.pathname])

  const toggleSection = (sectionId: string) => {
    setExpandedSection(prev => prev === sectionId ? null : sectionId)
  }

  return (
    <aside className="w-56 bg-sky-100 dark:bg-sky-900 text-gray-100 flex flex-col min-h-screen">
      <div className="p-4 border-b border-gray-700">
        <img src={logoImg} alt="Video Forge" className="w-full" />
        <span className="text-xs text-gray-400 block text-center mt-1">v0.3</span>
      </div>
      <nav className="flex-1 p-2 overflow-y-auto">
        {navigation.map((section) => {
          const isExpanded = expandedSection === section.id
          const isActiveSection = findActiveSectionId(location.pathname) === section.id

          return (
            <div key={section.id} className="mb-1">
              <button
                onClick={() => toggleSection(section.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded text-sm font-medium transition-colors ${
                  isActiveSection
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`}
              >
                <span>{section.title}</span>
                <ChevronIcon expanded={isExpanded} />
              </button>

              <div
                className={`overflow-hidden transition-all duration-200 ${
                  isExpanded ? 'max-h-40 opacity-100' : 'max-h-0 opacity-0'
                }`}
              >
                <ul className="mt-1 ml-3 space-y-1 border-l border-gray-700 pl-3">
                  {section.items.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        className={({ isActive }) =>
                          `block px-3 py-1.5 rounded text-sm transition-colors ${
                            isActive
                              ? 'bg-blue-600 text-white'
                              : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                          }`
                        }
                      >
                        {item.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )
        })}
      </nav>
    </aside>
  )
}
