import { promises as fs } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const webuiRoot = path.resolve(__dirname, '..')
const docsRoot = path.resolve(webuiRoot, '..', 'docs')
const contentRoot = path.resolve(webuiRoot, 'src', 'content')

const files = [
//  { name: 'profiles.md', src: path.join(docsRoot, 'profiles.md') },
//  { name: 'watchfolders.md', src: path.join(docsRoot, 'watchfolders.md') },
]

await fs.mkdir(contentRoot, { recursive: true })

for (const file of files) {
//  const dest = path.join(contentRoot, file.name)
//  await fs.copyFile(file.src, dest)
}
