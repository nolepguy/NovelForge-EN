/**
 * Parameter value formatting utility
 * 
 * Unified formatting logic for workflow node parameters
 */

export interface ParameterFormatOptions {
  type: string // Parameter type: string, integer, number, boolean, etc.
  value: any   // Raw value
}

export class ParameterFormatter {
  private static escapeString(value: any): string {
    const text = String(value)
    return text
      .replace(/\\/g, '\\\\')
      .replace(/\r/g, '\\r')
      .replace(/\n/g, '\\n')
      .replace(/\t/g, '\\t')
      .replace(/"/g, '\\"')
  }
  /**
   * Detect whether it is a variable reference
   * Format: variableName.propertyName (e.g., text.content, novel.chapter_list)
   */
  static isVariableReference(value: any): boolean {
    if (value === null || value === undefined) return false
    const strValue = String(value)
    return /^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+$/.test(strValue)
  }

  /**
   * Detect whether the value is empty
   * Note: 0 and false are not considered empty
   */
  static isEmpty(value: any): boolean {
    if (value === 0 || value === false) return false
    if (value === null || value === undefined) return true
    
    const strValue = String(value).trim()
    return strValue === ''
  }

  /**
   * Format a parameter value as Python code
   */
  static format(options: ParameterFormatOptions): string {
    const { type, value } = options

    // Empty value handling
    if (this.isEmpty(value)) {
      return ''
    }

    // Variable reference: use directly (the parser will add the $ marker automatically)
    if (this.isVariableReference(value)) {
      return String(value)
    }

    // Format based on type
    let result: string
    switch (type) {
      case 'integer':
      case 'number':
        result = String(value)
        break

      case 'boolean':
        // Convert to a Python boolean value
        result = (value === 'true' || value === true) ? 'True' : 'False'
        break

      case 'string':
        // String: add quotes, escape special characters
        result = `"${this.escapeString(value)}"`
        break

      case 'array':
        // Array type: supports arrays or comma-separated strings
        if (Array.isArray(value)) {
          // Already an array
          const items = value.map(item => `"${this.escapeString(item)}"`)
          result = `[${items.join(', ')}]`
        } else if (typeof value === 'string') {
          // Comma-separated string, convert to an array
          const items = value.split(',').map(item => item.trim()).filter(item => item)
          result = `[${items.map(item => `"${this.escapeString(item)}"`).join(', ')}]`
        } else {
          result = this.formatComplexType(value)
        }
        break
      
      case 'object':
        // Complex type: JSON serialization (needs to be converted to Python format)
        result = this.formatComplexType(value)
        break

      default:
        // Unknown type: check whether it is an object
        if (typeof value === 'object' && value !== null) {
          result = this.formatComplexType(value)
        } else {
          // Treat as string by default
          result = `"${this.escapeString(value)}"`
        }
        break
    }
    
    // Final safety check: ensure a string is returned
    if (typeof result !== 'string') {
      console.error('[ParameterFormatter.format] Result is not a string! Forcing conversion:', result)
      result = JSON.stringify(result)
    }
    
    return result
  }

  /**
   * Format a complex type (array, object)
   */
  private static formatComplexType(value: any): string {
    if (Array.isArray(value)) {
      const items = value.map(item => {
        // Recursively format array elements
        if (typeof item === 'object' && item !== null) {
          return this.formatComplexType(item)
        } else if (typeof item === 'string') {
          return `"${this.escapeString(item)}"`
        } else if (typeof item === 'number') {
          return String(item)
        } else if (typeof item === 'boolean') {
          return item ? 'True' : 'False'
        } else {
          return `"${this.escapeString(item)}"`
        }
      })
      return `[${items.join(', ')}]`
    }

    if (typeof value === 'object' && value !== null) {
      const pairs = Object.entries(value).map(([key, val]) => {
        // Recursively format object values
        let formattedVal: string
        if (typeof val === 'object' && val !== null) {
          formattedVal = this.formatComplexType(val)
        } else if (typeof val === 'string') {
          formattedVal = `"${this.escapeString(val)}"`
        } else if (typeof val === 'number') {
          formattedVal = String(val)
        } else if (typeof val === 'boolean') {
          formattedVal = val ? 'True' : 'False'
        } else {
          formattedVal = `"${this.escapeString(val)}"`
        }
        return `"${key}": ${formattedVal}`
      })
      return `{${pairs.join(', ')}}`
    }

    return String(value)
  }

  /**
   * Parse a display value (remove quotes)
   */
  static parseDisplayValue(value: any): string {
    if (value === null || value === undefined) return ''

    // Handle object types (dictionaries)
    if (typeof value === 'object' && !Array.isArray(value)) {
      try {
        // Convert to Python dictionary format
        return this.formatComplexType(value)
      } catch (e) {
        return JSON.stringify(value)
      }
    }

    // Handle array types
    if (Array.isArray(value)) {
      try {
        return this.formatComplexType(value)
      } catch (e) {
        return JSON.stringify(value)
      }
    }

    let strValue = String(value)

    // Remove string quotes
    if ((strValue.startsWith('"') && strValue.endsWith('"')) ||
        (strValue.startsWith("'") && strValue.endsWith("'"))) {
      return strValue.substring(1, strValue.length - 1)
    }

    return strValue
  }
}
