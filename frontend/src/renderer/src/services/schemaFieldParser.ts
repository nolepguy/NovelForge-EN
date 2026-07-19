/**
 * Schema field parsing service
 * Used to parse the field structure of a JSON Schema, supports nested objects, references and anyOf
 * Integrates with the existing schemaService to provide unified Schema parsing capabilities
 *
 * Unified parsing entry points:
 * - Card rendering: ModelDrivenForm.vue -> resolveActualSchema()
 * - Workflow preview: WorkflowParamPanel.vue -> parseSchemaFields()
 * - Array field parsing: ArrayField.vue -> resolveActualSchema() + createDefaultValue()
 * - Settings editing: uses the standalone outputModelSchemaUtils.ts (specifically for the Schema editor)
 */

import { schemaService } from '@renderer/api/schema'


export interface ParsedField {
  name: string
  title: string
  type: string
  path: string
  description: string
  required: boolean
  expanded: boolean
  children?: ParsedField[]
  expandable?: boolean
  arrayItemType?: string
  hasChildren?: boolean
}

/**
 * Parse JSON Schema field structure
 * @param schema JSON Schema object
 * @param path field path prefix
 * @param maxDepth maximum recursion depth
 * @returns the parsed field list
 */
export function parseSchemaFields(schema: any, path = '$.content', maxDepth = 5): ParsedField[] {
  if (maxDepth <= 0) return []
  
  const fields: ParsedField[] = []
  try {
    const properties = schema.properties || {}
    const defs = schema.$defs || {}
    const required = schema.required || []
    
    for (const [fieldName, fieldSchema] of Object.entries(properties)) {
      if (typeof fieldSchema !== 'object' || !fieldSchema) continue
      
      // Parse references and anyOf
      const resolvedSchema = resolveSchemaRef(fieldSchema as any, defs)
      
      const fieldType = resolvedSchema.type || 'unknown'
      const fieldTitle = resolvedSchema.title || fieldName
      const fieldDescription = resolvedSchema.description || ''
      const fieldPath = `${path}.${fieldName}`
      
      const fieldInfo: ParsedField = {
        name: fieldName,
        title: fieldTitle,
        type: fieldType,
        path: fieldPath,
        description: fieldDescription,
        required: required.includes(fieldName),
        expanded: false
      }
      
      // Handle nested objects
      if (fieldType === 'object' && resolvedSchema.properties) {
        const children = parseSchemaFields(resolvedSchema, fieldPath, maxDepth - 1)
        if (children.length > 0) {
          fieldInfo.children = children
          fieldInfo.expandable = true
          fieldInfo.hasChildren = true
        }
      }
      
      // Handle array types
      else if (fieldType === 'array' && resolvedSchema.items) {
        const itemsSchema = resolveSchemaRef(resolvedSchema.items, defs)
        if (itemsSchema.type === 'object' && itemsSchema.properties) {
          const children = parseSchemaFields(itemsSchema, `${fieldPath}[0]`, maxDepth - 1)
          if (children.length > 0) {
            fieldInfo.children = children
            fieldInfo.expandable = true
            fieldInfo.hasChildren = true
            fieldInfo.arrayItemType = 'object'
          }
        } else {
          fieldInfo.arrayItemType = itemsSchema.type || 'unknown'
        }
      }
      
      fields.push(fieldInfo)
    }
  } catch (e) {
    console.warn('Failed to parse Schema fields:', e)
  }
  
  return fields
}

/**
 * Resolve Schema references, supports local $defs and the global schemaService
 * @param schema Schema object
 * @param localDefs local $defs definitions
 * @returns the resolved Schema object
 */
export function resolveSchemaRef(schema: any, localDefs?: any): any {
  if (!schema || typeof schema !== 'object') return schema
  
  // Handle anyOf type - handle first
  if (schema.anyOf && Array.isArray(schema.anyOf)) {
    for (const anySchema of schema.anyOf) {
      if (anySchema.type === 'null') continue
      
      // Recursively resolve references inside anyOf
      const resolved = resolveSchemaRef(anySchema, localDefs)
      if (resolved && resolved.type && resolved.type !== 'null') {
        return {
          ...resolved,
          title: schema.title || resolved.title,
          description: schema.description || resolved.description
        }
      }
    }
  }
  
  // Handle $ref references
  if (schema.$ref && typeof schema.$ref === 'string') {
    const refPath = schema.$ref
    if (refPath.startsWith('#/$defs/')) {
      const refName = refPath.replace('#/$defs/', '')
      
      // Prefer local $defs
      let resolved = localDefs && localDefs[refName] ? localDefs[refName] : null
      
      // If not available locally, try fetching from the global schemaService
      if (!resolved) {
        resolved = schemaService.getSchema(refName)
      }
      
      if (resolved) {
        // Recursively resolve the referenced definition (may contain other references)
        const finalResolved = resolveSchemaRef(resolved, localDefs)
        return {
          ...finalResolved,
          title: schema.title || finalResolved.title,
          description: schema.description || finalResolved.description
        }
      }
    }
  }
  
  return schema
}

/**
 * Get the icon corresponding to a field type
 * @param type field type
 * @returns icon character
 */
export function getFieldIcon(type: string): string {
  switch (type) {
    case 'object': return '📁'
    case 'array': return '📊'
    case 'string': return '📄'
    case 'number': 
    case 'integer': return '🔢'
    case 'boolean': return '☑️'
    default: return '📄'
  }
}

/**
 * Toggle a field's expanded/collapsed state
 * @param fields field list
 * @param targetPath target field path
 */
export function toggleFieldExpanded(fields: ParsedField[], targetPath: string): void {
  for (const field of fields) {
    if (field.path === targetPath) {
      field.expanded = !field.expanded
      return
    }
    if (field.children) {
      toggleFieldExpanded(field.children, targetPath)
    }
  }
}

/**
 * Extract all field path options from parsed fields
 * @param fields the parsed field list
 * @param options the accumulated options array
 * @returns the field path options array
 */
export function extractFieldPathOptions(fields: ParsedField[], options: Array<{ label: string; value: string }> = []): Array<{ label: string; value: string }> {
  for (const field of fields) {
    // Only add non-object type fields, or objects without child fields
    if (field.type !== 'object' || !field.children?.length) {
      // Remove the $.content prefix, show relative path
      const label = field.path.replace(/^\$\.content\.?/, '') || field.name
      options.push({
        label: label,
        value: field.path
      })
    }
    
    // Recursively process child fields
    if (field.children?.length) {
      extractFieldPathOptions(field.children, options)
    }
  }
  
  return options
}

/**
 * Schema parsing function for ModelDrivenForm and similar components
 * Compatible with the original resolveActualSchema logic
 * @param schema Schema object
 * @param parentSchema parent Schema (used to get $defs)
 * @returns the resolved Schema object
 */
export function resolveActualSchema(schema: any, parentSchema?: any): any {
  const localDefs = parentSchema?.$defs || {}
  // Resolve the current node itself first (handle direct anyOf / $ref)
  const base = resolveSchemaRef(schema, localDefs)

  // For non-objects or empty values, return the resolved result directly
  if (!base || typeof base !== 'object') return base

  // Create a shallow copy to avoid accidentally modifying the original Schema
  const resolved: any = { ...base }

  // Recursively resolve child fields in properties (keep consistent with the root $defs)
  if (resolved.properties && typeof resolved.properties === 'object') {
    const nextProps: Record<string, any> = {}
    for (const [key, val] of Object.entries(resolved.properties)) {
      nextProps[key] = resolveSchemaRef(val as any, localDefs)
    }
    resolved.properties = nextProps
  }

  // Recursively resolve array items (especially the items.$ref → #/$defs/ModelName scenario)
  if (resolved.items) {
    resolved.items = resolveSchemaRef(resolved.items, localDefs)
  }

  // Recursively resolve tuple prefixItems
  if (Array.isArray(resolved.prefixItems)) {
    resolved.prefixItems = resolved.prefixItems.map((it: any) => resolveSchemaRef(it, localDefs))
  }

  // Recursively resolve sub-schemas inside anyOf
  if (Array.isArray(resolved.anyOf)) {
    resolved.anyOf = resolved.anyOf.map((it: any) => resolveSchemaRef(it, localDefs))
  }

  return resolved
}

