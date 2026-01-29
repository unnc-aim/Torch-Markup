import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'torch-markup-shortcuts'

// 默认快捷键配置
const DEFAULT_SHORTCUTS = {
  save: { key: 's', ctrl: true, description: '保存当前标注' },
  skip: { key: 'n', ctrl: false, description: '跳过当前图片' },
  undo: { key: 'z', ctrl: true, description: '撤销' },
  redo: { key: 'z', ctrl: true, shift: true, description: '重做' },
  help: { key: '?', ctrl: false, description: '显示帮助' }
}

export const useShortcutsStore = defineStore('shortcuts', () => {
  // 从 localStorage 加载或使用默认值
  const savedShortcuts = localStorage.getItem(STORAGE_KEY)
  const shortcuts = ref(savedShortcuts ? JSON.parse(savedShortcuts) : JSON.parse(JSON.stringify(DEFAULT_SHORTCUTS)))

  // 保存到 localStorage
  function saveShortcuts() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(shortcuts.value))
  }

  // 更新快捷键
  function updateShortcut(action, config) {
    shortcuts.value[action] = { ...shortcuts.value[action], ...config }
    saveShortcuts()
  }

  // 重置为默认
  function resetToDefault() {
    shortcuts.value = JSON.parse(JSON.stringify(DEFAULT_SHORTCUTS))
    saveShortcuts()
  }

  // 检查按键是否匹配某个动作
  function matchShortcut(event, action) {
    const shortcut = shortcuts.value[action]
    if (!shortcut) return false

    const key = event.key.toLowerCase()
    const ctrlKey = event.ctrlKey || event.metaKey
    const shiftKey = event.shiftKey

    return (
      key === shortcut.key.toLowerCase() &&
      ctrlKey === !!shortcut.ctrl &&
      shiftKey === !!shortcut.shift
    )
  }

  // 检测是否为 macOS
  const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.platform)

  // 获取快捷键显示文本
  function getShortcutText(action) {
    const shortcut = shortcuts.value[action]
    if (!shortcut) return ''

    const parts = []
    if (shortcut.ctrl) parts.push(isMac ? '⌘' : 'Ctrl')
    if (shortcut.shift) parts.push(isMac ? '⇧' : 'Shift')
    parts.push(shortcut.key.toUpperCase())

    return parts.join('+')
  }

  return {
    shortcuts,
    updateShortcut,
    resetToDefault,
    matchShortcut,
    getShortcutText,
    DEFAULT_SHORTCUTS
  }
})
