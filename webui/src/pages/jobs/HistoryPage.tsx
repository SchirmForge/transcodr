export function HistoryPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Jobs History</h1>
      <p className="text-gray-600">Completed and failed jobs will appear here.</p>
      <div className="mt-6 p-4 bg-white rounded-lg shadow">
        <p className="text-gray-500 text-sm">No job history</p>
      </div>
    </div>
  )
}
