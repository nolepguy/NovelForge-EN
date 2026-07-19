import { defineStore, storeToRefs } from 'pinia'
import { ref, computed, watch } from 'vue'
import {
  getCardTypes,
  getCardsForProject,
  createCard,
  updateCard,
  deleteCard,
  getContentModels,
  type CardRead,
  type CardTypeRead,
  type CardCreate,
  type CardUpdate,
} from '@renderer/api/cards'
import { useProjectStore } from './useProjectStore'
import { ElMessage } from 'element-plus'
import { BASE_URL } from '@renderer/api/request'

// Helper function to build a tree from a flat list of cards
// To avoid adding a children property directly on CardRead, define a local extended type here
type CardNode = CardRead & { children: CardNode[] }
const buildCardTree = (cards: CardRead[]): CardNode[] => {
  const cardMap = new Map<number, CardNode>()
  // Convert the flat list returned by the backend into a node list and attach a children array
  const nodes: CardNode[] = cards.map((c) => ({ ...(c as CardRead), children: [] as CardNode[] }))
  nodes.forEach((node) => {
    cardMap.set(node.id, node)
  })

  const tree: CardNode[] = []
  nodes.forEach((node) => {
    if (node.parent_id && cardMap.has(node.parent_id)) {
      cardMap.get(node.parent_id)!.children.push(node)
    } else {
      tree.push(node)
    }
  })

  // Sort the nodes at each level by display_order
  const sortNodes = (nodes: CardNode[]) => {
    nodes.sort((a, b) => a.display_order - b.display_order)
    nodes.forEach((n) => sortNodes(n.children))
  }
  sortNodes(tree)

  return tree
}


export const useCardStore = defineStore('card', () => {
  const projectStore = useProjectStore()
  const { currentProject } = storeToRefs(projectStore)

  // --- State ---
  const cards = ref<CardRead[]>([])
  const cardTypes = ref<CardTypeRead[]>([])
  const availableModels = ref<string[]>([])
  const activeCardId = ref<number | null>(null)
  const isLoading = ref(false)

  // --- Getters ---
  const cardTree = computed(() => buildCardTree(cards.value) as unknown as CardRead[])
  const activeCard = computed(() => {
    if (activeCardId.value === null) return null
    return cards.value.find((c) => c.id === activeCardId.value) || null
  })

  // --- Watchers ---
  watch(currentProject, (newProject) => {
    if (newProject?.id) {
      fetchCards(newProject.id);
    } else {
      // If there's no project, clear the cards
      cards.value = [];
    }
  }, { immediate: true });

  // --- Internal helper: get the ID by card type name ---
  function getCardTypeIdByName(name: string): number | null {
    const ct = cardTypes.value.find(t => t.name === name)
    return ct ? ct.id : null
  }

  // --- Internal helper: regex-parse the "Volume N" title ---
  function parseVolumeIndexFromTitle(title: string): number | null {
    const m = title.match(/^Volume (\d+)$/)
    if (!m) return null
    return parseInt(m[1], 10)
  }

  // --- Actions ---

  async function fetchInitialData() {
    await Promise.all([
        fetchCardTypes(),
        fetchAvailableModels()
    ]);
  }

  // Card Actions
  async function fetchCards(projectId: number) {
    if (!projectId) {
        cards.value = []
        return
    }
    isLoading.value = true
    try {
      const fetchedCards = await getCardsForProject(projectId)
      cards.value = fetchedCards
    } catch (error) {
      ElMessage.error('Failed to fetch cards.')
      console.error(error)
    } finally {
      isLoading.value = false
    }
  }

  // New: addCard supports options.silent; in silent mode it does not do a full refresh or show a toast, but inserts locally and returns the new card directly
  async function addCard(cardData: CardCreate, options?: { silent?: boolean }) {
    if (!currentProject.value?.id) return
    try {
      const newCard = await createCard(currentProject.value.id, cardData)
      if (options?.silent) {
        // Insert directly into local state to avoid the "loading" getting stuck from frequent full refreshes
        cards.value = [...cards.value, newCard as unknown as CardRead]
      } else {
        await fetchCards(currentProject.value.id)
        ElMessage.success(`Card "${newCard.title}" created.`)
      }
      return newCard
    } catch (error) {
      if (!options?.silent) ElMessage.error('Failed to create card.')
      console.error(error)
      return
    }
  }

  // Add an optional parameter: skipHooks is used to skip the "post-save hook" during internal updates
  async function modifyCard(cardId: number, cardData: { content: Record<string, any> | null } | CardUpdate, options?: { skipHooks?: boolean }) {
    try {
      // Use the raw response to read the X-Workflows-Started header
      const axiosResp: any = await (await import('@renderer/api/cards')).updateCardRaw(cardId, cardData as CardUpdate)
      const updatedCard: CardRead = axiosResp.data

      // Sync the local update
      if ('parent_id' in cardData || 'display_order' in cardData) {
        if (currentProject.value?.id) await fetchCards(currentProject.value.id)
      } else {
        const index = cards.value.findIndex((c) => c.id === cardId)
        if (index !== -1) {
          const existingCard = cards.value[index]
          const newContent = (cardData as any).content !== undefined ? (cardData as any).content : existingCard.content
          cards.value[index] = { ...existingCard, ...updatedCard, content: newContent }
        }
      }
      ElMessage.success(`Card "${updatedCard.title}" updated.`)

      // Read the workflow run receipt and subscribe to events; refresh when done
      const hdr = axiosResp.headers || {}
      const runHeader: string | undefined = hdr['x-workflows-started'] || hdr['X-Workflows-Started'] || hdr['x-workflows-started'.toLowerCase()]
      const runIds: number[] = typeof runHeader === 'string' && runHeader.trim()
        ? runHeader.split(',').map((s: string) => Number(s.trim())).filter((n: number) => Number.isFinite(n))
        : []

      // Fallback polling function
      const pollUntilDone = async (runId: number, maxSecs = 30) => {
        const start = Date.now()
        while (Date.now() - start < maxSecs * 1000) {
          try {
            const resp = await fetch(`${BASE_URL}/api/workflows/runs/${runId}`, { method: 'GET' })
            const json = await resp.json()
            const st = json?.status
            if (st === 'succeeded' || st === 'failed' || st === 'cancelled') {
              if (currentProject.value?.id) await fetchCards(currentProject.value.id)
              return
            }
          } catch (e) { 
            console.error('[Workflow] Polling error:', e)
          }
          await new Promise(r => setTimeout(r, 1000))
        }
      }

      if (runIds.length && currentProject.value?.id) {
        for (const rid of runIds) {
          try {
            const es = new EventSource(`${BASE_URL}/api/workflows/runs/${rid}/events`)
            let finished = false
            es.addEventListener('run_completed', async (evt: MessageEvent) => {
              finished = true
              try {
                const payload = (() => { try { return JSON.parse(String(evt.data || '{}')) } catch { return {} } })()
                const affected: number[] = Array.isArray(payload?.affected_card_ids) ? payload.affected_card_ids.filter((n: any) => Number.isFinite(Number(n))).map((n: any) => Number(n)) : []
                if (affected.length > 0) {
                   // Targeted refresh: fetch details of affected cards and merge into local state
                  for (const cid of affected) {
                    try {
                      const resp = await fetch(`${BASE_URL}/api/cards/${cid}`, { method: 'GET' })
                      if (resp.ok) {
                        const updated = await resp.json()
                        const i = cards.value.findIndex(c => c.id === cid)
                        if (i >= 0) {
                          const prev = cards.value[i]
                          cards.value[i] = { ...prev, ...updated, content: updated?.content ?? prev.content }
                        } else {
                          // If the card is not in the local list, fall back to a full refresh
                          if (currentProject.value?.id) await fetchCards(currentProject.value.id)
                        }
                      }
                    } catch (e) { 
                      console.error('[Workflow] Failed to refresh affected card:', cid, e)
                    }
                  }
                } else {
                  // No affected set provided; fall back to a full refresh
                  if (currentProject.value?.id) await fetchCards(currentProject.value.id)
                }
              } finally { es.close() }
            })
            es.onerror = async (err) => {
              if (finished) {
                es.close()
                return
              }
              console.error('[Workflow] SSE connection error:', err)
              es.close()
              await pollUntilDone(rid)
            }
          } catch (e) {
            console.error('[Workflow] Failed to open SSE:', e)
            await pollUntilDone(rid)
          }
        }
      }
    } catch (error) {
      ElMessage.error('Failed to update card.')
      console.error(error)
    }
  }

  async function removeCard(cardId: number) {
    await deleteCard(cardId)
    // The backend already did recursive deletion; just refresh here
    if (currentProject.value?.id) await fetchCards(currentProject.value.id)
  }

  // CardType Actions
  async function fetchCardTypes() {
    try {
      cardTypes.value = await getCardTypes()
    } catch (error) {
      ElMessage.error('Failed to fetch card types.')
      console.error(error)
    }
  }
  
  // Available Models Actions
  async function fetchAvailableModels() {
    try {
      availableModels.value = await getContentModels()
    } catch (error) {
      ElMessage.error('Failed to fetch available content models.')
      console.error(error)
    }
  }

  // Utility
  function setActiveCard(cardId: number | null) {
    activeCardId.value = cardId
  }

  return {
    // State
    cards,
    cardTypes,
    availableModels,
    activeCardId,
    isLoading,
    // Getters
    cardTree,
    activeCard,
    // Actions
    fetchInitialData,
    fetchCards,
    addCard,
    modifyCard,
    removeCard,
    fetchCardTypes,
    fetchAvailableModels,
    setActiveCard,
  }
}) 