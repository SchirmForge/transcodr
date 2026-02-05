export function WatchfoldersPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Watch Folders</h1>
      <p className="text-gray-600">Configured watch folders and their status.</p>
      <div className="mt-6 p-4 bg-white rounded-lg shadow">
        <p className="text-gray-500 text-sm">No watch folders configured</p>
      </div>
    </div>
  )
}
