/**
 * GitHub Release update check service
 * Cross-platform support (Electron + Web)
 */

import i18n from '@renderer/i18n'

export interface ReleaseInfo {
  version: string
  name: string
  body: string // Release notes (Markdown)
  publishedAt: string
  htmlUrl: string
  downloadUrl?: string
}

export interface UpdateCheckResult {
  hasUpdate: boolean
  currentVersion: string
  latestVersion?: string
  releaseInfo?: ReleaseInfo
}

const GITHUB_REPO = 'RhythmicWave/NovelForge'
const GITHUB_API_BASE = 'https://api.github.com'
const REQUEST_TIMEOUT = 10000 // 10s timeout

/**
 * Get the current version from package.json
 */
export function getCurrentVersion(): string {
  // At build time, the version is injected into import.meta.env
  // Fall back to a default value if absent
  return import.meta.env.VITE_APP_VERSION || '0.8.5'
}

/**
 * Compare version numbers, supporting tags with suffixes such as 0.8.5-fix2.
 * Rules:
 *   1) First compare the numeric core version (split by x.y.z);
 *   2) If the core versions are equal, a version with a suffix is treated as
 *      higher than one without (0.8.5-fix2 > 0.8.5);
 *   3) If both have suffixes, try to parse the trailing number for comparison
 *      (fix2 > fix1); otherwise compare as strings.
 * @returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal
 */
function compareVersions(v1: string, v2: string): number {
  const parseVersion = (v: string) => {
    const cleaned = v.replace(/^v/, '')
    const [core, suffixRaw] = cleaned.split('-', 2)
    const coreParts = core.split('.').map((s) => {
      const n = parseInt(s, 10)
      return Number.isNaN(n) ? 0 : n
    })
    return { coreParts, suffix: suffixRaw || '' }
  }

  const a = parseVersion(v1)
  const b = parseVersion(v2)

  // 1) Compare the core version numbers
  const maxLen = Math.max(a.coreParts.length, b.coreParts.length)
  for (let i = 0; i < maxLen; i++) {
    const num1 = a.coreParts[i] ?? 0
    const num2 = b.coreParts[i] ?? 0
    if (num1 > num2) return 1
    if (num1 < num2) return -1
  }

  // 2) When the core versions are equal, compare the suffixes
  if (a.suffix === b.suffix) return 0
  if (a.suffix && !b.suffix) return 1
  if (!a.suffix && b.suffix) return -1

  // 3) Both have suffixes; prefer comparing the trailing number
  const re = /^([a-zA-Z\-]*)(\d*)$/
  const ma = a.suffix.match(re)
  const mb = b.suffix.match(re)
  if (ma && mb) {
    const labelA = ma[1]
    const labelB = mb[1]
    const numA = ma[2] ? parseInt(ma[2], 10) : 0
    const numB = mb[2] ? parseInt(mb[2], 10) : 0
    if (labelA === labelB && (numA !== numB)) {
      return numA > numB ? 1 : -1
    }
  }

  // 4) Fall back to plain string comparison
  if (a.suffix > b.suffix) return 1
  if (a.suffix < b.suffix) return -1
  return 0
}

/**
 * fetch with a timeout
 */
async function fetchWithTimeout(url: string, timeout: number): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)
  
  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'NovelForge-App'
      }
    })
    clearTimeout(timeoutId)
    return response
  } catch (error) {
    clearTimeout(timeoutId)
    throw error
  }
}

/**
 * Fetch the latest GitHub Release
 */
async function fetchLatestRelease(timeout: number = REQUEST_TIMEOUT): Promise<ReleaseInfo | null> {
  const url = `${GITHUB_API_BASE}/repos/${GITHUB_REPO}/releases/latest`
  
  try {
    const response = await fetchWithTimeout(url, timeout)
    
    if (!response.ok) {
      // For HTTP errors, throw an exception instead of treating it as "no update",
      // so the caller can show a clear error message (e.g. 403 rate limit).
      if (response.status === 403) {
        throw new Error(i18n.global.t('app.update.githubRateLimited'))
      }
      throw new Error(i18n.global.t('app.update.githubApiError', { status: response.status }))
    }
    
    const data = await response.json()
    
    return {
      version: data.tag_name?.replace(/^v/, '') || data.name,
      name: data.name || data.tag_name,
      body: data.body || '',
      publishedAt: data.published_at,
      htmlUrl: data.html_url,
      downloadUrl: data.assets?.[0]?.browser_download_url
    }
  } catch (error: any) {
    if (error.name === 'AbortError') {
      throw new Error(i18n.global.t('app.update.requestTimeout'))
    }
    throw error
  }
}

/**
 * Check for updates (with retry mechanism)
 * @param maxRetries Maximum number of retries (0 means no retry)
 */
export async function checkForUpdates(maxRetries: number = 0): Promise<UpdateCheckResult> {
  const currentVersion = getCurrentVersion()
  let lastError: Error | null = null
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const releaseInfo = await fetchLatestRelease()
      
      if (!releaseInfo) {
        return {
          hasUpdate: false,
          currentVersion
        }
      }
      
      const hasUpdate = compareVersions(releaseInfo.version, currentVersion) > 0
      
      return {
        hasUpdate,
        currentVersion,
        latestVersion: releaseInfo.version,
        releaseInfo: hasUpdate ? releaseInfo : undefined
      }
    } catch (error: any) {
      lastError = error
      console.warn(`Update check failed (attempt ${attempt + 1}/${maxRetries + 1}):`, error.message)

      // If there are remaining retries, wait a while before retrying
      if (attempt < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, 2000 * (attempt + 1)))
      }
    }
  }
  
  // All retries failed
  throw lastError || new Error(i18n.global.t('app.update.checkFailed'))
}

/**
 * Automatically check for updates (with 1 retry)
 */
export async function autoCheckForUpdates(): Promise<UpdateCheckResult> {
  return checkForUpdates(1)
}

/**
 * Manually check for updates (no retry)
 */
export async function manualCheckForUpdates(): Promise<UpdateCheckResult> {
  return checkForUpdates(0)
}
