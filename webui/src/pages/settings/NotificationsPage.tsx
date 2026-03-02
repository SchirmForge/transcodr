import { useState, useEffect } from 'react'
import { useConfig, useUpdateConfig } from '../../hooks/useConfig'

type NotificationsForm = {
  enabled: boolean
  on_job_complete: boolean
  on_batch_complete: boolean
  on_queue_empty: boolean
  on_error: boolean
  desktop: {
    enabled: boolean
  }
  email: {
    enabled: boolean
    smtp_server: string
    smtp_port: number
    use_tls: boolean
    smtp_user: string
    smtp_password: string
    from_address: string
    recipients_text: string   // textarea: one per line
  }
  apprise: {
    enabled: boolean
    urls_text: string         // textarea: one per line
  }
}

const DEFAULT_FORM: NotificationsForm = {
  enabled: false,
  on_job_complete: false,
  on_batch_complete: true,
  on_queue_empty: true,
  on_error: true,
  desktop: { enabled: false },
  email: {
    enabled: false,
    smtp_server: 'smtp.gmail.com',
    smtp_port: 587,
    use_tls: true,
    smtp_user: '',
    smtp_password: '',
    from_address: 'transcodr@example.com',
    recipients_text: '',
  },
  apprise: {
    enabled: false,
    urls_text: '',
  },
}

function Toggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        value ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
      }`}
    >
      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
        value ? 'translate-x-6' : 'translate-x-1'
      }`} />
    </button>
  )
}

export function NotificationsPage() {
  const { data: config, isLoading, isError, error } = useConfig()
  const updateConfig = useUpdateConfig()

  const [form, setForm] = useState<NotificationsForm>(DEFAULT_FORM)
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const configToForm = (cfg: typeof config): NotificationsForm => {
    if (!cfg) return DEFAULT_FORM
    const n = cfg.notifications
    return {
      enabled: n.enabled,
      on_job_complete: n.on_job_complete,
      on_batch_complete: n.on_batch_complete,
      on_queue_empty: n.on_queue_empty,
      on_error: n.on_error,
      desktop: { enabled: n.desktop.enabled },
      email: {
        enabled: n.email.enabled,
        smtp_server: n.email.smtp_server,
        smtp_port: n.email.smtp_port,
        use_tls: n.email.use_tls,
        smtp_user: n.email.smtp_user,
        smtp_password: n.email.smtp_password,
        from_address: n.email.from_address,
        recipients_text: n.email.recipients.join('\n'),
      },
      apprise: {
        enabled: n.apprise.enabled,
        urls_text: n.apprise.urls.join('\n'),
      },
    }
  }

  useEffect(() => {
    if (config) {
      setForm(configToForm(config))
      setDirty(false)
    }
  }, [config])

  const set = (patch: Partial<NotificationsForm>) => {
    setForm(prev => ({ ...prev, ...patch }))
    setDirty(true)
    setMessage(null)
  }

  const setEmail = (patch: Partial<NotificationsForm['email']>) => {
    setForm(prev => ({ ...prev, email: { ...prev.email, ...patch } }))
    setDirty(true)
    setMessage(null)
  }

  const setApprise = (patch: Partial<NotificationsForm['apprise']>) => {
    setForm(prev => ({ ...prev, apprise: { ...prev.apprise, ...patch } }))
    setDirty(true)
    setMessage(null)
  }

  const handleSave = () => {
    const payload = {
      notifications: {
        enabled: form.enabled,
        on_job_complete: form.on_job_complete,
        on_batch_complete: form.on_batch_complete,
        on_queue_empty: form.on_queue_empty,
        on_error: form.on_error,
        desktop: { enabled: form.desktop.enabled },
        email: {
          enabled: form.email.enabled,
          smtp_server: form.email.smtp_server,
          smtp_port: form.email.smtp_port,
          use_tls: form.email.use_tls,
          smtp_user: form.email.smtp_user,
          smtp_password: form.email.smtp_password,
          from_address: form.email.from_address,
          recipients: form.email.recipients_text.split('\n').map(s => s.trim()).filter(Boolean),
        },
        apprise: {
          enabled: form.apprise.enabled,
          urls: form.apprise.urls_text.split('\n').map(s => s.trim()).filter(Boolean),
        },
      },
    }
    updateConfig.mutate(payload, {
      onSuccess: (data) => {
        setDirty(false)
        const warnings = data.warnings?.length ? ` (${data.warnings.join('; ')})` : ''
        setMessage({ type: 'success', text: `Configuration saved.${warnings}` })
      },
      onError: (err) => {
        setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to save' })
      },
    })
  }

  const handleCancel = () => {
    setForm(configToForm(config))
    setDirty(false)
    setMessage(null)
  }

  if (isLoading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Notifications</h1>
        <div className="mt-6 p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <p className="text-gray-500 dark:text-gray-400 text-sm">Loading...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Notifications</h1>
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg shadow border border-red-200 dark:border-red-800">
          <p className="text-red-600 dark:text-red-400 text-sm">
            Failed to load configuration: {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    )
  }

  const inputCls = 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm'
  const labelCls = 'block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1'
  const hintCls = 'mt-1 text-xs text-gray-500 dark:text-gray-400'

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Notifications</h1>
      <p className="text-gray-600 dark:text-gray-400 mb-6">
        Configure when and how Transcodr sends notifications.
      </p>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          message.type === 'success'
            ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800'
            : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800'
        }`}>
          {message.text}
        </div>
      )}

      <div className="space-y-6">

        {/* Master switch */}
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Enable Notifications</h2>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Master switch — enables all configured channels.</p>
            </div>
            <Toggle value={form.enabled} onChange={v => set({ enabled: v })} />
          </div>
        </div>

        {/* Events */}
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Events</h2>
          <div className="space-y-4">
            {([
              ['on_job_complete', 'Job Complete', 'Notify after every individual job finishes.'],
              ['on_batch_complete', 'Batch Complete', 'Notify when all jobs from one submission finish.'],
              ['on_queue_empty', 'Queue Empty', 'Notify once when the queue drains completely.'],
              ['on_error', 'Error', 'Notify on critical daemon errors.'],
            ] as [keyof NotificationsForm, string, string][]).map(([field, label, hint]) => (
              <div key={field} className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</span>
                  <p className="text-xs text-gray-500 dark:text-gray-400">{hint}</p>
                </div>
                <Toggle value={form[field] as boolean} onChange={v => set({ [field]: v })} />
              </div>
            ))}
          </div>
        </div>

        {/* Desktop */}
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Desktop</h2>
            <Toggle value={form.desktop.enabled} onChange={v => { set({ desktop: { enabled: v } }); }} />
          </div>
          <p className={hintCls}>
            Sends desktop notifications via <code>notify-send</code> (libnotify).
            Install: <code>sudo apt install libnotify-bin</code>.
          </p>
        </div>

        {/* Email */}
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Email (SMTP)</h2>
            <Toggle value={form.email.enabled} onChange={v => setEmail({ enabled: v })} />
          </div>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>SMTP Server</label>
                <input type="text" value={form.email.smtp_server}
                  onChange={e => setEmail({ smtp_server: e.target.value })}
                  className={inputCls} placeholder="smtp.gmail.com" />
              </div>
              <div>
                <label className={labelCls}>SMTP Port</label>
                <input type="number" min={1} max={65535} value={form.email.smtp_port}
                  onChange={e => setEmail({ smtp_port: parseInt(e.target.value) || 587 })}
                  className="w-32 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm" />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Use TLS (STARTTLS)</span>
              </div>
              <Toggle value={form.email.use_tls} onChange={v => setEmail({ use_tls: v })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelCls}>SMTP User</label>
                <input type="text" value={form.email.smtp_user}
                  onChange={e => setEmail({ smtp_user: e.target.value })}
                  className={inputCls} placeholder="user@example.com" />
              </div>
              <div>
                <label className={labelCls}>SMTP Password</label>
                <input type="password" value={form.email.smtp_password}
                  onChange={e => setEmail({ smtp_password: e.target.value })}
                  className={inputCls} placeholder="••••••••" />
                <p className={hintCls}>Or set the <code>TRANSCODR_SMTP_PASSWORD</code> environment variable.</p>
              </div>
            </div>
            <div>
              <label className={labelCls}>From Address</label>
              <input type="text" value={form.email.from_address}
                onChange={e => setEmail({ from_address: e.target.value })}
                className={inputCls} placeholder="transcodr@example.com" />
            </div>
            <div>
              <label className={labelCls}>Recipients</label>
              <textarea
                value={form.email.recipients_text}
                onChange={e => setEmail({ recipients_text: e.target.value })}
                rows={3}
                className={`${inputCls} font-mono`}
                placeholder={"alice@example.com\nbob@example.com"}
              />
              <p className={hintCls}>One email address per line.</p>
            </div>
          </div>
        </div>

        {/* Apprise */}
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Apprise</h2>
            <Toggle value={form.apprise.enabled} onChange={v => setApprise({ enabled: v })} />
          </div>
          <p className={`${hintCls} mb-4`}>
            Supports 80+ services via the <a href="https://github.com/caronc/apprise" target="_blank" rel="noreferrer" className="underline">Apprise</a> library.
            Install: <code>pip install apprise</code>.
          </p>
          <div>
            <label className={labelCls}>Notification URLs</label>
            <textarea
              value={form.apprise.urls_text}
              onChange={e => setApprise({ urls_text: e.target.value })}
              rows={4}
              className={`${inputCls} font-mono`}
              placeholder={"ntfy://ntfy.sh/my-topic\ngotifys://gotify.server.com/apptoken\npover://UserKey@AppToken"}
            />
            <p className={hintCls}>One Apprise URL per line.</p>
          </div>
        </div>

      </div>

      <div className="mt-6 flex gap-3">
        <button
          onClick={handleSave}
          disabled={!dirty || updateConfig.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {updateConfig.isPending ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={handleCancel}
          disabled={!dirty}
          className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
