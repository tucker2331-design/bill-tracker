import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The speed switch (repo-root cadence_profiles.json, read by the jobs every tick) is baked into the site at build
// time, so Health's freshness limits follow the same word. Toggling the speed is a merge, and every merge rebuilds
// the site — the two cannot disagree. An unreadable file bakes in {} (every state reads "fast", the learned rhythm).
function readSpeedProfiles(): Record<string, unknown> {
  try {
    return JSON.parse(readFileSync(fileURLToPath(new URL('../cadence_profiles.json', import.meta.url)), 'utf-8'))
  } catch {
    return {}
  }
}
const speedProfiles = readSpeedProfiles()

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: { __SPEED_PROFILES__: JSON.stringify(speedProfiles) },
})
