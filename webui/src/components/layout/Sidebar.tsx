import { useState, useEffect } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useStatus } from '../../hooks/useStatus'
import logoImg from '../../assets/transcodr-final-alpha.png'

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
      { label: 'Create Job', to: '/jobs/create' },
      { label: 'History', to: '/jobs/history' },
    ],
  },
  {
    id: 'encoding-rules',
    title: 'Encoding Rules',
    items: [
      { label: 'Watch Folders', to: '/encoding-rules/watchfolders' },
      { label: 'Profiles', to: '/encoding-rules/profiles' },
    ],
  },
  {
    id: 'settings',
    title: 'Settings',
    items: [
      { label: 'Skin & Status', to: '/settings/general' },
      { label: 'Storage', to: '/settings/storage' },
      { label: 'Encoding', to: '/settings/encoding' },
      { label: 'Daemon', to: '/settings/daemon' },
      { label: 'Logging', to: '/settings/logging' },
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

/* function ChevronIcon({ expanded }: { expanded: boolean }) {
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
} */

function findActiveSectionId(pathname: string): string | null {
  if (pathname.startsWith('/jobs')) {
    return 'jobs'
  }
  for (const section of navigation) {
    if (section.items.some(item => pathname.startsWith(item.to))) {
      return section.id
    }
  }
  return null
}

export function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { data: status } = useStatus()
  const [expandedSection, setExpandedSection] = useState<string | null>(null)

  // Auto-expand section based on current route
  useEffect(() => {
    const activeSection = findActiveSectionId(location.pathname)
    if (activeSection) {
      setExpandedSection(activeSection)
    }
  }, [location.pathname])

  const toggleSection = (sectionId: string) => {
    if (sectionId === 'jobs') {
      setExpandedSection('jobs')
      navigate('/jobs/activity')
      return
    }
    if (sectionId === 'settings') {
      setExpandedSection('settings')
      navigate('/settings/general')
      return
    }
    setExpandedSection(prev => prev === sectionId ? null : sectionId)
  }  

  return (
    <aside className="w-56 bg-graphite-200 dark:bg-graphite-950 text-steel-800 dark:text-steel-100 flex flex-col min-h-screen">
      <div className="p-4">
        <img src={logoImg} alt="TransCoDR" className="w-full" />
        <span className="text-xs text-steel-400 block text-center mt-1">{status ? `v${status.version}` : ''}</span>
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
                    ? 'bg-graphite-300 text-steel-700 dark:bg-graphite-800 dark:text-steel-100'
                    : 'text-steel-600 hover:bg-graphite-100 hover:text-steel-900 dark:text-steel-300 dark:hover:bg-graphite-800 dark:hover:text-steel-100'
                }`}
              >
                 <span>{section.title}</span>
                {/* <ChevronIcon expanded={isExpanded} /> */}
              </button>

              <div
                className={`overflow-hidden transition-all duration-200 ${
                  isExpanded ? 'max-h-60 opacity-100' : 'max-h-0 opacity-0'
                }`}
              >
                <ul className="mt-1 ml-3 space-y-1 border-l border-graphite-400 dark:border-graphite-800 pl-3">
                  {section.items.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        className={({ isActive }) =>
                          `block px-3 py-1.5 rounded text-sm transition-colors ${
                            isActive
                              ? 'bg-zinc-200 text-graphite-950 dark:bg-zinc-600 dark:text-graphite-300'
                              : 'text-steel-600 hover:bg-graphite-100 hover:text-steel-900 dark:text-steel-400 dark:hover:bg-graphite-800 dark:hover:text-steel-100'
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
