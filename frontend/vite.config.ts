import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

const repositoryRoot = fileURLToPath(new URL('../', import.meta.url))

export default defineConfig(({ mode }) => {
  const serverEnvironment = loadEnv(mode, repositoryRoot, '')
  const coreAdminKey = serverEnvironment.ADMIN_API_KEY?.trim()

  return {
    envDir: repositoryRoot,
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api/v1/settings/llm': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          headers: coreAdminKey
            ? { 'X-Admin-Key': coreAdminKey }
            : undefined,
        },
        '/api/v1/simulation': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          headers: coreAdminKey
            ? { 'X-Admin-Key': coreAdminKey }
            : undefined,
        },
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
