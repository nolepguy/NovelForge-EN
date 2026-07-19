export function unwrapChapterOutline(obj: any): any {
  if (!obj || typeof obj !== 'object') return {}
  // Common wrapper keys
  if (obj.chapter_outline && typeof obj.chapter_outline === 'object') return obj.chapter_outline
  if (obj.ChapterOutline && typeof obj.ChapterOutline === 'object') return obj.ChapterOutline
  if (obj.chapterOutline && typeof obj.chapterOutline === 'object') return obj.chapterOutline
  // Direct detection: presence of key fields indicates chapter outline form
  const hallmark = ['volume_number', 'chapter_number', 'character_list', 'overview', 'characters', 'participants', 'roles']
  const keys = Object.keys(obj || {})
  return keys.some(k => hallmark.includes(k)) ? obj : {}
}

// Unified name cleaning: strip parenthetical notes, full-width/half-width spaces, trailing commas, etc.
export function sanitizeName(raw: string): string {
  if (!raw) return ''
  let s = String(raw).trim()
  // Remove full-width spaces
  s = s.replace(/\u3000/g, ' ')
  s = s.replace(/\s+/g, ' ').trim()
  // Remove parentheses and their contents (Chinese and English)
  s = s.replace(/[（(][^）)]*[）)]/g, '').trim()
  // Strip trailing meaningless punctuation
  s = s.replace(/[、，。,.]+$/g, '').trim()
  return s
}

export function toNameList(arr: any): string[] {
  if (!Array.isArray(arr)) return []
  if (arr.every(x => typeof x === 'string')) return (arr as string[]).map(s => sanitizeName(s)).filter(Boolean)
  const out: string[] = []
  for (const it of arr) {
    if (typeof it === 'object' && it) {
      const cand = (it.name || it.title || it.label || '').toString().trim()
      if (cand) out.push(sanitizeName(cand))
    }
  }
  return Array.from(new Set(out))
}

export function extractParticipantsFrom(obj: any): string[] {
  if (!obj || typeof obj !== 'object') return []
  const keys = ['character_list','characters','participants','roles']
  for (const k of keys) {
    if (k in obj) {
      const names = toNameList((obj as any)[k])
      if (names.length) return names
    }
  }
  return []
} 