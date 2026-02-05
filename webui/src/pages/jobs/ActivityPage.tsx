export function ActivityPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Jobs Activity</h1>
      <p className="text-gray-600">Running and queued jobs will appear here.</p>
      <div className="mt-6 p-4 bg-white rounded-lg shadow">
        <p className="text-gray-500 text-sm">No active jobs</p>
      </div>
    </div>
  )
}
