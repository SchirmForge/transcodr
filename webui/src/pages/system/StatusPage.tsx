export function StatusPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">System Status</h1>
      <p className="text-gray-600">Daemon status and system information.</p>
      <div className="mt-6 p-4 bg-white rounded-lg shadow">
        <p className="text-gray-500 text-sm">Connecting to daemon...</p>
      </div>
    </div>
  )
}
