import { dirname, resolve } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const backendDir = resolve(rootDir, 'backend')
const frontendDir = resolve(rootDir, 'frontend')
const python = resolve(backendDir, '.venv', 'Scripts', 'python.exe')
const node = process.execPath
const apiHost = process.env.MIRROR_API_HOST || '127.0.0.1'
const apiPort = Number(process.env.MIRROR_API_PORT || 8000)
const frontendHost = process.env.MIRROR_FRONTEND_HOST || '127.0.0.1'
const frontendPort = Number(process.env.MIRROR_FRONTEND_PORT || 5173)
const apiOrigin = `http://${apiHost}:${apiPort}`
const processes = []
let stopping = false

if (!Number.isInteger(apiPort) || !Number.isInteger(frontendPort)) {
  throw new Error('MIRROR_API_PORT and MIRROR_FRONTEND_PORT must be valid port numbers.')
}

function stopProcesses() {
  stopping = true
  for (const child of processes) {
    if (child.exitCode === null && !child.killed) child.kill()
  }
}

function startProcess(command, args, options) {
  const child = spawn(command, args, { ...options, stdio: 'inherit' })
  processes.push(child)
  child.on('error', (error) => {
    console.error(`Unable to start ${command}: ${error.message}`)
    stopProcesses()
    process.exitCode = 1
  })
  child.on('exit', (code, signal) => {
    if (stopping) return
    console.error(`${command} exited${signal ? ` after ${signal}` : ` with code ${code}`}. Stopping MIRROR dev servers.`)
    stopProcesses()
    process.exitCode = code || 1
  })
  return child
}

async function waitForBackend(backend) {
  const deadline = Date.now() + 60_000
  let lastError = 'no health response'

  while (Date.now() < deadline) {
    if (backend.exitCode !== null) {
      throw new Error(`Backend exited before becoming healthy (exit code ${backend.exitCode}).`)
    }

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 1_500)
    try {
      const response = await fetch(`${apiOrigin}/health`, { signal: controller.signal })
      if (response.ok) {
        const health = await response.json()
        if (health.status === 'ok') return
        lastError = `unexpected health response: ${JSON.stringify(health)}`
      } else {
        lastError = `health endpoint returned HTTP ${response.status}`
      }
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error)
    } finally {
      clearTimeout(timeout)
    }

    await new Promise((resolveDelay) => setTimeout(resolveDelay, 500))
  }

  throw new Error(`Backend did not become healthy within 60 seconds (${lastError}).`)
}

process.on('SIGINT', stopProcesses)
process.on('SIGTERM', stopProcesses)

try {
  const backendEnv = {
    ...process.env,
    FRONTEND_ORIGIN: process.env.FRONTEND_ORIGIN || `http://${frontendHost}:${frontendPort}`,
  }
  if (process.env.MIRROR_DATABASE_URL) {
    backendEnv.DATABASE_URL = process.env.MIRROR_DATABASE_URL
  }
  const backend = startProcess(
    python,
    ['-m', 'uvicorn', 'app.main:app', '--host', apiHost, '--port', String(apiPort), '--reload'],
    { cwd: backendDir, env: backendEnv },
  )

  console.log(`Waiting for MIRROR API health at ${apiOrigin}/health...`)
  await waitForBackend(backend)
  if (stopping) process.exitCode = 1
  else {
    console.log('MIRROR API is healthy. Starting the frontend.')
    startProcess(
      node,
      [resolve(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', frontendHost, '--port', String(frontendPort)],
      {
        cwd: frontendDir,
        env: {
          ...process.env,
          MIRROR_API_PROXY_TARGET: apiOrigin,
        },
      },
    )
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error))
  stopProcesses()
  process.exitCode = 1
}
