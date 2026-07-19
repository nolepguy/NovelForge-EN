import request from './request'
import { ref } from 'vue'

// --- Type definitions ---
// Basic JSON Schema type definitions. Can be extended as needed.
export interface JSONSchema {
  // Common properties
  type?: string | string[]
  title?: string
  description?: string
  default?: any
  examples?: any[]
  enum?: any[]
  const?: any
  minLength?: number
  'x-knowledge-source'?: string

  // Object properties
  properties?: { [key: string]: JSONSchema }
  required?: string[]
  // For arrays
  items?: JSONSchema
  // For Pydantic v2+ tuples (Tuple)
  prefixItems?: JSONSchema[]
  // For Pydantic v1 tuples (Tuple) or union types (Union)
  anyOf?: JSONSchema[]
  // For enums converted from Literal
  // For object references
  $ref?: string
}

// --- State ---
const schemas = ref<Map<string, JSONSchema>>(new Map())
const isLoading = ref(false)
const error = ref<any>(null)

// --- Logic ---

/**
 * Resolve a $ref reference and find its corresponding schema definition.
 * @param refPath The reference path (e.g., '#/components/schemas/MyModel')
 * @param openapiSpec The full OpenAPI spec object.
 * @returns The resolved JSONSchema, or null if not found.
 */
function resolveRef(refPath: string, allSchemas: Map<string, JSONSchema>): JSONSchema | null {
  // We only handle references pointing to other definitions in allSchemas
  // Assume the format is '#/$defs/MyModel' or 'MyModel'
  const refName = refPath.split('/').pop()
  if (!refName) {
    console.error('Invalid $ref path:', refPath)
    return null
  }
  const resolved = allSchemas.get(refName)
  if (!resolved) {
    console.error(`Unable to resolve $ref in allSchemas: ${refName}`)
        return null
      }
  return resolved
}

/**
 * Recursively resolve all $ref references in a schema.
 * @param schema The JSONSchema to resolve.
 * @param allSchemas A Map containing all available schema definitions.
 * @param visited Reference paths already visited, used to prevent circular references.
 * @returns The resolved JSONSchema.
 */
function dereferenceSchema(
  schema: JSONSchema,
  allSchemas: Map<string, JSONSchema>,
  visited = new Set<string>()
): JSONSchema {
  if (typeof schema !== 'object' || schema === null) {
    return schema
  }

  if (schema.$ref) {
    if (visited.has(schema.$ref)) {
      console.warn('Circular reference detected:', schema.$ref)
      return { type: 'object', title: 'Circular Reference' }
    }
    visited.add(schema.$ref)
    const resolved = resolveRef(schema.$ref, allSchemas)
    if (resolved) {
      // Recursively resolve the resolved schema
      return dereferenceSchema(resolved, allSchemas, visited)
    } else {
      return { type: 'string', title: `Unresolved Reference: ${schema.$ref}` }
    }
  }

  const newSchema = { ...schema }
  if (newSchema.properties) {
    newSchema.properties = Object.fromEntries(
      Object.entries(newSchema.properties).map(([key, propSchema]) => [
        key,
        dereferenceSchema(propSchema, allSchemas, new Set(visited))
      ])
    )
  }

  if (newSchema.items) {
    newSchema.items = dereferenceSchema(newSchema.items, allSchemas, new Set(visited))
  }
  
  if (newSchema.prefixItems) {
    newSchema.prefixItems = newSchema.prefixItems.map(itemSchema => 
      dereferenceSchema(itemSchema, allSchemas, new Set(visited))
    );
  }

  if (newSchema.anyOf) {
    newSchema.anyOf = newSchema.anyOf.map(itemSchema => 
      dereferenceSchema(itemSchema, allSchemas, new Set(visited))
    );
  }

  return newSchema
}


/**
 * Fetch the full OpenAPI spec and populate the schemas Map.
 * This function should be called once at application startup.
 */
async function loadSchemas() {
  if (schemas.value.size > 0 || isLoading.value) {
    return
  }
  isLoading.value = true
  error.value = null
  try {
    // Fetch all schemas from a dedicated endpoint, using the default /api prefix
    const allSchemas = await request.get<Record<string, JSONSchema>>('/ai/schemas')
    if (allSchemas) {
      const schemaMap = new Map<string, JSONSchema>(Object.entries(allSchemas))
      
      // Create a new Map to store dereferenced schemas
      const dereferencedSchemaMap = new Map<string, JSONSchema>()

      // Step 1: First populate all schemas into the Map
      for (const [name, schema] of schemaMap.entries()) {
        dereferencedSchemaMap.set(name, schema);
      }
      
      // Step 2: Iterate and dereference each schema
      for (const [name, schema] of dereferencedSchemaMap.entries()) {
        dereferencedSchemaMap.set(name, dereferenceSchema(schema, dereferencedSchemaMap));
      }

      // DEBUG: Log all the schema keys that were loaded
      console.log('[SchemaService] All schema keys loaded from /ai/schemas:', Array.from(dereferencedSchemaMap.keys()));

      schemas.value = dereferencedSchemaMap
    }
  } catch (e) {
    console.error('Failed to load schemas from /ai/schemas:', e)
    error.value = e
  } finally {
    isLoading.value = false
  }
}

// Force refresh (clear cache and reload)
async function refreshSchemas() {
  try {
    schemas.value = new Map()
    isLoading.value = false
    await loadSchemas()
  } catch (e) {
    console.error('Failed to refresh schemas:', e)
  }
}

/**
 * Get the name of a schema.
 * @param name The schema name (e.g., 'VolumeOutline').
 * @returns The JSONSchema if found, otherwise undefined.
 */
function getSchema(name: string): JSONSchema | undefined {
  return schemas.value.get(name)
}

// --- Exports ---
// Export a singleton object for interacting with the schema.
export const schemaService = {
  schemas,
  isLoading,
  error,
  loadSchemas,
  refreshSchemas,
  getSchema
} 
