/**
 * Instruction Executor
 *
 * Responsible for applying instructions sent from the backend to data objects.
 * All validation is done on the backend; here we only mechanically execute instructions.
 */

import { set, get } from 'lodash-es'
import type { Instruction } from '@renderer/types/instruction'

/**
 * Instruction executor class
 */
export class InstructionExecutor {
  private data: Record<string, any> = {}

  /**
   * Create the executor
   * @param initialData Initial data
   */
  constructor(initialData: Record<string, any> = {}) {
    this.data = { ...initialData }
  }

  /**
   * Execute a single instruction
   * @param instruction Instruction object
   */
  execute(instruction: Instruction): void {
    switch (instruction.op) {
      case 'set':
        this.executeSet(instruction.path, instruction.value)
        break
      case 'append':
        this.executeAppend(instruction.path, instruction.value)
        break
      case 'done':
        // The done instruction requires no action
        break
    }
  }

  /**
   * Execute the set instruction
   * @param path JSON Pointer path
   * @param value The value to set
   */
  private executeSet(path: string, value: any): void {
    const lodashPath = this.convertPath(path)
    set(this.data, lodashPath, value)
  }

  /**
   * Execute the append instruction
   * @param path JSON Pointer path
   * @param value The element to append
   */
  private executeAppend(path: string, value: any): void {
    const lodashPath = this.convertPath(path)
    const arr = get(this.data, lodashPath) || []
    
    if (!Array.isArray(arr)) {
      console.warn(`Path ${path} is not an array, cannot perform append operation`)
      return
    }
    
    arr.push(value)
    set(this.data, lodashPath, arr)
  }

  /**
   * Convert a JSON Pointer path to a lodash path
   * @param pointer JSON Pointer format (e.g. /name or /config/theme)
   * @returns lodash path format (e.g. name or config.theme)
   */
  private convertPath(pointer: string): string {
    // Remove the leading /
    if (pointer.startsWith('/')) {
      pointer = pointer.slice(1)
    }

    // Replace / with .
    return pointer.replace(/\//g, '.')
  }

  /**
   * Get the current data
   * @returns The data object
   */
  getData(): Record<string, any> {
    return this.data
  }

  /**
   * Reset the data
   * @param newData New data
   */
  reset(newData: Record<string, any> = {}): void {
    this.data = { ...newData }
  }

  /**
   * Clear the data
   */
  clear(): void {
    this.data = {}
  }
}
