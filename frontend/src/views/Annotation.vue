<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAnnotationStore } from '../stores/annotation'
import { useShortcutsStore } from '../stores/shortcuts'
import { ElMessage } from 'element-plus'
import AnnotationCanvas from '../components/AnnotationCanvas.vue'
import api from '../utils/api'

const route = useRoute()
const router = useRouter()
const store = useAnnotationStore()
const shortcutsStore = useShortcutsStore()

const datasetId = computed(() => parseInt(route.params.datasetId))
const progress = ref(null)
const showHelp = ref(false)
const showShortcutSettings = ref(false)
const editingShortcut = ref(null)
const editingCategoryShortcut = ref(null)  // 正在编辑快捷键的类别ID

// 模式切换（默认拖动模式）
const canvasMode = ref('pan')  // 'annotate' | 'pan'
const zoomLevel = ref(1)
const canvasRef = ref(null)

onMounted(async () => {
  await loadData()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  store.reset()
})

async function loadData() {
  try {
    await store.loadCategories(datasetId.value)
    await store.fetchNextImage(datasetId.value)
    await loadProgress()
    // 加载新图片后重置为拖动模式
    canvasMode.value = 'pan'
  } catch (error) {
    ElMessage.error('加载数据失败')
  }
}

async function loadProgress() {
  try {
    const response = await api.get(`/images/dataset/${datasetId.value}/progress`)
    progress.value = response.data
  } catch (error) {
    console.error('Failed to load progress', error)
  }
}

async function handleSave() {
  try {
    const savedCount = await store.saveAnnotations(false)
    ElMessage.success(`保存成功 (${savedCount} 个标注)`)
    // 如果在历史模式，不自动跳转下一张
    if (!store.isInHistory) {
      await store.fetchNextImage(datasetId.value)
      // 进入下一张图片后重置为拖动模式
      canvasMode.value = 'pan'
    }
    await loadProgress()
  } catch (error) {
    console.error('Save failed:', error)
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function handleSkip() {
  try {
    await store.saveAnnotations(true)
    ElMessage.info('已标记为未见')
    await store.fetchNextImage(datasetId.value)
    await loadProgress()
    // 进入下一张图片后重置为拖动模式
    canvasMode.value = 'pan'
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

async function handlePrevious() {
  try {
    // 如果已经在历史模式中，先保存当前标注再返回
    if (store.isInHistory) {
      const savedCount = await store.saveAnnotations(false)
      ElMessage.success(`保存成功 (${savedCount} 个标注)`)
    }
    await store.goToPreviousImage()
  } catch (error) {
    console.error('Save or navigate failed:', error)
    ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function handleNext() {
  if (store.isInHistory) {
    // 在历史模式中，先保存当前标注，再前往下一张
    try {
      const savedCount = await store.saveAnnotations(false)
      ElMessage.success(`保存成功 (${savedCount} 个标注)`)
      await store.goToNextImage()
    } catch (error) {
      console.error('Save or navigate failed:', error)
      ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
    }
  } else {
    // 正常流程，继续获取新图片
    await handleSaveAndNext()
  }
}

async function handleSaveAndNext() {
  try {
    await store.saveAnnotations(false)
    ElMessage.success('保存成功')
    store.exitHistoryMode()
    await store.fetchNextImage(datasetId.value)
    await loadProgress()
    // 进入下一张图片后重置为拖动模式
    canvasMode.value = 'pan'
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

function handleKeydown(e) {
  // 忽略输入框中的按键
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
    return
  }

  // 正在编辑类别快捷键时，交给对应的处理器
  if (editingCategoryShortcut.value) {
    return
  }

  // 使用自定义快捷键
  if (shortcutsStore.matchShortcut(e, 'save')) {
    e.preventDefault()
    handleSave()
    return
  }

  if (shortcutsStore.matchShortcut(e, 'skip')) {
    handleSkip()
    return
  }

  if (shortcutsStore.matchShortcut(e, 'undo')) {
    e.preventDefault()
    store.undo()
    return
  }

  if (shortcutsStore.matchShortcut(e, 'redo')) {
    e.preventDefault()
    store.redo()
    return
  }

  if (shortcutsStore.matchShortcut(e, 'help')) {
    showHelp.value = !showHelp.value
    return
  }

  const key = e.key.toLowerCase()

  if (key === 'escape') {
    showHelp.value = false
    showShortcutSettings.value = false
    return
  }

  // 模式切换快捷键
  if (key === 'v') {
    canvasMode.value = 'annotate'
    return
  }
  if (key === 'h') {
    canvasMode.value = 'pan'
    return
  }

  // 数字或字母快捷键选择类别
  const selected = store.selectCategoryByKey(key)
  if (selected) {
    // 选择类别后切换到标注模式
    canvasMode.value = 'annotate'
  }
}

// 快捷键设置相关
function startEditShortcut(action) {
  editingShortcut.value = action
}

function handleShortcutKeydown(e) {
  e.preventDefault()
  if (!editingShortcut.value) return

  if (e.key === 'Escape') {
    editingShortcut.value = null
    return
  }

  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key
  shortcutsStore.updateShortcut(editingShortcut.value, {
    key,
    ctrl: e.ctrlKey || e.metaKey,
    shift: e.shiftKey
  })
  editingShortcut.value = null
  ElMessage.success('快捷键已更新')
}

function resetShortcuts() {
  shortcutsStore.resetToDefault()
  ElMessage.success('快捷键已重置为默认')
}

function selectCategory(category) {
  // 如果正在编辑快捷键，不选择类别
  if (editingCategoryShortcut.value) return
  store.selectedCategory = category
  // 选择类别后切换到标注模式
  canvasMode.value = 'annotate'
}

function startEditCategoryShortcut(category, e) {
  e.stopPropagation()
  editingCategoryShortcut.value = category.id
}

function handleCategoryShortcutKeydown(category, e) {
  e.preventDefault()
  e.stopPropagation()

  if (e.key === 'Escape') {
    editingCategoryShortcut.value = null
    return
  }

  // 只接受单个字符或数字
  if (e.key.length === 1) {
    const newKey = e.key.toLowerCase()
    // 检查是否与其他类别快捷键冲突
    const conflict = store.categories.find(c =>
      c.id !== category.id && c.shortcut_key === newKey
    )
    if (conflict) {
      ElMessage.warning(`快捷键 "${newKey}" 已被 "${conflict.name}" 使用`)
      return
    }

    // 更新快捷键
    updateCategoryShortcut(category.id, newKey)
  }
}

async function updateCategoryShortcut(categoryId, shortcutKey) {
  try {
    await api.put(`/categories/${categoryId}`, { shortcut_key: shortcutKey })
    // 更新本地数据
    const cat = store.categories.find(c => c.id === categoryId)
    if (cat) {
      cat.shortcut_key = shortcutKey
    }
    ElMessage.success('快捷键已更新')
  } catch (error) {
    ElMessage.error('更新快捷键失败')
  }
  editingCategoryShortcut.value = null
}

function goBack() {
  router.push('/')
}

function fitToView() {
  if (canvasRef.value) {
    canvasRef.value.fitToContainer()
    zoomLevel.value = canvasRef.value.scale
  }
}

function handleZoomChange(zoom) {
  zoomLevel.value = zoom
}
</script>

<template>
  <div class="annotation-container">
    <!-- 首次加载全屏进度 -->
    <div v-if="store.isInitialLoad && store.isPrefetching" class="initial-loading">
      <div class="loading-content">
        <h2>正在加载图片...</h2>
        <el-progress
          :percentage="store.prefetchProgress"
          :stroke-width="20"
          :text-inside="true"
          style="width: 400px"
        />
        <p>预加载中，请稍候</p>
      </div>
    </div>

    <!-- 顶部工具栏 -->
    <header class="toolbar" v-show="!store.isInitialLoad || !store.isPrefetching">
      <div class="left">
        <el-button @click="goBack" :icon="'ArrowLeft'">返回</el-button>
        <span class="image-info" v-if="store.currentImage">
          {{ store.currentImage.filename }}
          <span v-if="store.currentImage.width">
            ({{ store.currentImage.width }} x {{ store.currentImage.height }})
          </span>
        </span>
      </div>
      <div class="center">
        <el-button-group>
          <el-button @click="store.undo()" :disabled="!store.canUndo" :icon="'RefreshLeft'">
            撤销
          </el-button>
          <el-button @click="store.redo()" :disabled="!store.canRedo" :icon="'RefreshRight'">
            重做
          </el-button>
        </el-button-group>

        <div class="mode-toolbar">
          <el-radio-group v-model="canvasMode" size="small">
            <el-radio-button value="annotate">
              <span class="mode-btn">✏️ 标注 (V)</span>
            </el-radio-button>
            <el-radio-button value="pan">
              <span class="mode-btn">✋ 拖动 (H)</span>
            </el-radio-button>
          </el-radio-group>

          <span class="zoom-info">{{ Math.round(zoomLevel * 100) }}%</span>
          <el-button size="small" @click="fitToView">适应</el-button>
        </div>
      </div>
      <div class="right">
        <el-button-group class="nav-buttons">
          <el-button @click="handlePrevious" :disabled="!store.canGoPrevious" :icon="'ArrowLeft'">
            上一张
          </el-button>
          <el-button @click="handleNext" :disabled="store.isInHistory && !store.canGoNext" :icon="'ArrowRight'">
            下一张
          </el-button>
        </el-button-group>
        <span v-if="store.isInHistory" class="history-indicator">浏览历史中</span>
        <el-button @click="showShortcutSettings = true" :icon="'Setting'">快捷键</el-button>
        <el-button @click="showHelp = true" :icon="'QuestionFilled'">帮助</el-button>
        <el-button @click="handleSkip" type="warning">未见 ({{ shortcutsStore.getShortcutText('skip') }})</el-button>
        <el-button @click="handleSave" type="primary">保存 ({{ shortcutsStore.getShortcutText('save') }})</el-button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content" v-show="!store.isInitialLoad || !store.isPrefetching">
      <!-- 左侧类别面板 -->
      <aside class="category-panel">
        <h3>类别选择</h3>
        <div class="category-list">
          <div
            v-for="category in store.categories"
            :key="category.id"
            class="category-item"
            :class="{ active: store.selectedCategory?.id === category.id }"
            @click="selectCategory(category)"
          >
            <span class="color-dot" :style="{ background: category.color }"></span>
            <span class="name">{{ category.name }}</span>
            <span
              class="shortcut"
              :class="{ editing: editingCategoryShortcut === category.id }"
              @click="startEditCategoryShortcut(category, $event)"
              @keydown="handleCategoryShortcutKeydown(category, $event)"
              tabindex="0"
            >
              <template v-if="editingCategoryShortcut === category.id">
                ...
              </template>
              <template v-else>
                {{ category.shortcut_key || '+' }}
              </template>
            </span>
          </div>
        </div>

        <div class="annotations-list" v-if="store.annotations.length > 0">
          <h3>当前标注 ({{ store.annotations.length }})</h3>
          <div
            v-for="(ann, index) in store.annotations"
            :key="ann.id"
            class="annotation-item"
          >
            <span class="index">#{{ index + 1 }}</span>
            <span class="category">
              {{ store.categories.find(c => c.id === ann.category_id)?.name || '未知' }}
            </span>
            <el-button
              type="danger"
              size="small"
              :icon="'Delete'"
              circle
              @click="store.removeAnnotation(ann.id)"
            />
          </div>
        </div>
      </aside>

      <!-- 画布区域 -->
      <div class="canvas-container">
        <div v-if="store.isLoading" class="loading-overlay">
          <el-icon class="is-loading" :size="48"><Loading /></el-icon>
        </div>

        <div v-else-if="!store.currentImage" class="empty-state">
          <el-empty description="没有更多图片需要标注">
            <el-button type="primary" @click="goBack">返回首页</el-button>
          </el-empty>
        </div>

        <AnnotationCanvas
          v-else
          ref="canvasRef"
          :image-id="store.currentImage.id"
          :annotations="store.annotations"
          :categories="store.categories"
          :selected-category="store.selectedCategory"
          :mode="canvasMode"
          @add="store.addAnnotation"
          @update="store.updateAnnotation"
          @delete="store.removeAnnotation"
          @zoom-change="handleZoomChange"
        />
      </div>

      <!-- 右侧进度面板 -->
      <aside class="progress-panel">
        <h3>标注进度</h3>
        <div v-if="progress" class="progress-info">
          <el-progress
            type="circle"
            :percentage="progress.progress"
            :width="120"
          />
          <div class="stats">
            <div class="stat-row">
              <span>总计:</span>
              <span>{{ progress.total }}</span>
            </div>
            <div class="stat-row">
              <span>已标注:</span>
              <span class="success">{{ progress.labeled }}</span>
            </div>
            <div class="stat-row">
              <span>未见:</span>
              <span class="warning">{{ progress.skipped }}</span>
            </div>
            <div class="stat-row">
              <span>待处理:</span>
              <span class="info">{{ progress.pending }}</span>
            </div>
          </div>
        </div>

        <div class="queue-status" v-if="store.queueLength > 0">
          <h4>缓存队列</h4>
          <span class="queue-count">{{ store.queueLength }} 张</span>
        </div>
      </aside>
    </main>

    <!-- 后台预加载进度条（底部） -->
    <div v-if="!store.isInitialLoad && store.isPrefetching" class="prefetch-bar">
      <span>缓存加载中...</span>
      <el-progress
        :percentage="store.prefetchProgress"
        :stroke-width="6"
        style="width: 200px"
      />
      <span class="queue-info">队列: {{ store.queueLength }}</span>
    </div>

    <!-- 快捷键帮助弹窗 -->
    <el-dialog v-model="showHelp" title="快捷键帮助" width="500px">
      <div class="help-content">
        <table class="shortcuts-table">
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('save') }}</kbd></td>
            <td>保存当前标注</td>
          </tr>
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('skip') }}</kbd></td>
            <td>标记未见（画面中无目标）</td>
          </tr>
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('undo') }}</kbd></td>
            <td>撤销</td>
          </tr>
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('redo') }}</kbd></td>
            <td>重做</td>
          </tr>
          <tr>
            <td><kbd>Delete</kbd> / <kbd>Backspace</kbd></td>
            <td>删除选中的标注框</td>
          </tr>
          <tr>
            <td><kbd>鼠标滚轮</kbd></td>
            <td>缩放画布</td>
          </tr>
          <tr>
            <td><kbd>空格</kbd> + 拖动</td>
            <td>平移画布</td>
          </tr>
          <tr>
            <td><kbd>V</kbd></td>
            <td>切换到标注模式</td>
          </tr>
          <tr>
            <td><kbd>H</kbd></td>
            <td>切换到拖动模式</td>
          </tr>
          <tr>
            <td><kbd>类别快捷键</kbd></td>
            <td>快速切换类别并进入标注模式</td>
          </tr>
          <tr>
            <td><kbd>{{ shortcutsStore.getShortcutText('help') }}</kbd></td>
            <td>显示/隐藏帮助</td>
          </tr>
        </table>
        <div class="help-tip">
          <el-button text type="primary" @click="showHelp = false; showShortcutSettings = true">
            自定义快捷键
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 快捷键设置弹窗 -->
    <el-dialog v-model="showShortcutSettings" title="快捷键设置" width="500px">
      <div class="shortcut-settings">
        <table class="shortcuts-table">
          <tr v-for="(config, action) in shortcutsStore.shortcuts" :key="action">
            <td class="action-name">{{ config.description }}</td>
            <td class="shortcut-key">
              <div
                class="key-input"
                :class="{ editing: editingShortcut === action }"
                @click="startEditShortcut(action)"
                @keydown="handleShortcutKeydown"
                tabindex="0"
              >
                <template v-if="editingShortcut === action">
                  按下新快捷键...
                </template>
                <template v-else>
                  <kbd>{{ shortcutsStore.getShortcutText(action) }}</kbd>
                </template>
              </div>
            </td>
          </tr>
        </table>
        <div class="settings-footer">
          <el-button @click="resetShortcuts">恢复默认</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.annotation-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1a1a2e;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #16213e;
  border-bottom: 1px solid #0f3460;
}

.toolbar .left,
.toolbar .center,
.toolbar .right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mode-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 16px;
  padding-left: 16px;
  border-left: 1px solid #0f3460;
}

.mode-btn {
  font-size: 12px;
}

.zoom-info {
  color: #a0a0a0;
  font-size: 12px;
  min-width: 50px;
  text-align: center;
}

.nav-buttons {
  margin-right: 8px;
}

.history-indicator {
  color: #e6a23c;
  font-size: 12px;
  padding: 4px 8px;
  background: rgba(230, 162, 60, 0.2);
  border-radius: 4px;
}

.image-info {
  color: #a0a0a0;
  font-size: 14px;
}

.main-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.category-panel,
.progress-panel {
  width: 240px;
  padding: 16px;
  background: #16213e;
  overflow-y: auto;
}

.category-panel h3,
.progress-panel h3 {
  color: white;
  margin-bottom: 16px;
  font-size: 14px;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.category-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background: #0f3460;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.category-item:hover {
  background: #1a4a7a;
}

.category-item.active {
  background: #e94560;
}

.color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 10px;
}

.category-item .name {
  flex: 1;
  color: white;
}

.category-item .shortcut {
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
  font-size: 12px;
  color: #ccc;
  cursor: pointer;
  min-width: 20px;
  text-align: center;
  transition: all 0.2s;
}

.category-item .shortcut:hover {
  background: rgba(255, 255, 255, 0.4);
}

.category-item .shortcut.editing {
  background: #e94560;
  color: white;
  outline: none;
}

.category-item .shortcut:focus {
  outline: 2px solid #e94560;
  outline-offset: 2px;
}

.annotations-list {
  margin-top: 24px;
}

.annotation-item {
  display: flex;
  align-items: center;
  padding: 8px;
  background: #0f3460;
  border-radius: 4px;
  margin-bottom: 8px;
}

.annotation-item .index {
  color: #888;
  margin-right: 8px;
}

.annotation-item .category {
  flex: 1;
  color: white;
}

.canvas-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.loading-overlay,
.empty-state {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(26, 26, 46, 0.9);
}

.loading-overlay .el-icon {
  color: #e94560;
}

.progress-panel .progress-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.stats {
  width: 100%;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  color: #a0a0a0;
  border-bottom: 1px solid #0f3460;
}

.stat-row .success {
  color: #67c23a;
}

.stat-row .warning {
  color: #e6a23c;
}

.stat-row .info {
  color: #409eff;
}

.queue-status {
  margin-top: 24px;
  padding: 12px;
  background: #0f3460;
  border-radius: 6px;
}

.queue-status h4 {
  color: #a0a0a0;
  font-size: 12px;
  margin-bottom: 8px;
}

.queue-count {
  color: #67c23a;
  font-size: 18px;
  font-weight: bold;
}

.help-content {
  padding: 16px;
}

.shortcuts-table {
  width: 100%;
  border-collapse: collapse;
}

.shortcuts-table td {
  padding: 10px;
  border-bottom: 1px solid #eee;
}

.shortcuts-table td:first-child {
  width: 200px;
}

kbd {
  display: inline-block;
  padding: 2px 6px;
  background: #f5f5f5;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 12px;
}

/* 首次加载全屏进度 */
.initial-loading {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: #1a1a2e;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.loading-content {
  text-align: center;
  color: white;
}

.loading-content h2 {
  margin-bottom: 24px;
}

.loading-content p {
  margin-top: 16px;
  color: #a0a0a0;
}

/* 后台预加载进度条（底部） */
.prefetch-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 32px;
  background: #16213e;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  z-index: 1000;
  color: #a0a0a0;
  font-size: 13px;
}

.prefetch-bar .queue-info {
  color: #67c23a;
}

/* 快捷键设置 */
.shortcut-settings {
  padding: 16px;
}

.shortcuts-table .action-name {
  width: 150px;
}

.shortcuts-table .shortcut-key {
  width: 200px;
}

.key-input {
  padding: 8px 16px;
  background: #f5f5f5;
  border: 2px solid #ddd;
  border-radius: 6px;
  cursor: pointer;
  text-align: center;
  transition: all 0.2s;
}

.key-input:hover {
  border-color: #409eff;
}

.key-input.editing {
  border-color: #e94560;
  background: #fff5f5;
  color: #e94560;
}

.settings-footer {
  margin-top: 24px;
  text-align: center;
}

.help-tip {
  margin-top: 16px;
  text-align: center;
}
</style>
