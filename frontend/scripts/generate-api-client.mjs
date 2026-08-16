import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(frontendRoot, '..')
const backendRoot = join(repositoryRoot, 'backend')
const outputPath = join(frontendRoot, 'src', 'generated')
const suppliedSchema = process.env.OPENAPI_SCHEMA_PATH
const temporaryDirectory = suppliedSchema ? null : mkdtempSync(join(tmpdir(), 'chat-openapi-'))
const schemaPath = suppliedSchema ? resolve(suppliedSchema) : join(temporaryDirectory, 'openapi.json')

function run(command, args, cwd) {
  const result = spawnSync(command, args, { cwd, stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}

try {
  if (!suppliedSchema) {
    run(
      'uv',
      [
        'run',
        '--project',
        backendRoot,
        '--frozen',
        'python',
        join(backendRoot, 'scripts', 'export_openapi.py'),
        schemaPath,
      ],
      repositoryRoot,
    )
  }

  run(
    join(frontendRoot, 'node_modules', '.bin', 'openapi-ts'),
    ['--input', schemaPath, '--output', outputPath, '--client', '@hey-api/client-fetch'],
    frontendRoot,
  )
} finally {
  if (temporaryDirectory) rmSync(temporaryDirectory, { recursive: true, force: true })
}
