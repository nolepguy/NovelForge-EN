<template>
  <div class="card-editor-host">
    <component :is="activeEditorComponent" :key="card.id" :card="card" :prefetched="prefetched" />
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue';
import type { CardRead } from '@renderer/api/cards';

const props = defineProps<{
  card: CardRead;
  prefetched?: any;
}>();

// --- Editor Component Map ---
// This map allows us to resolve a string name to an actual component.
// Only editors that need a fully custom shell are registered here
// If only the content editor differs (e.g. the CodeMirrorEditor for chapter body),
// it should be configured via GenericCardEditor's content_editor_component
const editorMap: Record<string, any> = {
  TagsEditor: defineAsyncComponent(() => import('../editors/TagsEditor.vue')),
  ReviewResultCardEditor: defineAsyncComponent(() => import('./ReviewResultCardEditor.vue')),
  // Add other custom editors here in the future
};

// --- Default Editor ---
const GenericCardEditor = defineAsyncComponent(() => import('./GenericCardEditor.vue'));


const activeEditorComponent = computed(() => {
  const customEditorName = props.card.card_type.editor_component;
  if (customEditorName && editorMap[customEditorName]) {
    return editorMap[customEditorName];
  }
  return GenericCardEditor;
});
</script>

<style scoped>
.card-editor-host {
  height: 100%;
  width: 100%;
}
</style> 
