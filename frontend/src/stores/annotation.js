import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../utils/api'

const PREFETCH_SIZE = 20       // 预加载数量
const PREFETCH_THRESHOLD = 5   // 剩余多少张时触发预加载

export const useAnnotationStore = defineStore('annotation', () => {
  const currentImage = ref(null)
  const annotations = ref([])
  const categories = ref([])
  const selectedCategory = ref(null)
  const history = ref([])
  const historyIndex = ref(-1)
  const isLoading = ref(false)

  // 预加载相关
  const imageQueue = ref([])           // 预加载队列
  const prefetchProgress = ref(0)      // 预加载进度 0-100
  const isPrefetching = ref(false)     // 是否正在预加载
  const isInitialLoad = ref(true)      // 是否首次加载
  const prefetchedImages = ref(new Map()) // 已预加载的图片 Blob

  // 已处理图片历史（用于返回上一张）
  const processedHistory = ref([])     // 已处理图片历史栈
  const historyPosition = ref(-1)      // 当前位置 (-1 表示在最新)
  const isInHistory = ref(false)       // 是否正在浏览历史

  // 计算属性
  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)
  const queueLength = computed(() => imageQueue.value.length)
  // 可以返回上一张的条件：有已处理的历史记录
  const canGoPrevious = computed(() => {
    // 只要有历史记录就可以尝试返回
    return processedHistory.value.length > 0
  })
  const canGoNext = computed(() => isInHistory.value && historyPosition.value < processedHistory.value.length - 1)

  // 加载类别
  async function loadCategories(datasetId) {
    const response = await api.get(`/categories/dataset/${datasetId}`)
    categories.value = response.data

    // 如果只有一个类别，自动选中
    if (categories.value.length === 1) {
      selectedCategory.value = categories.value[0]
    }

    return categories.value
  }

  // 批量获取图片列表（用于预加载）
  async function fetchImageBatch(datasetId, count = PREFETCH_SIZE) {
    try {
      const response = await api.get(`/images/next/${datasetId}/batch`, {
        params: { count }
      })
      return response.data || []
    } catch (error) {
      console.error('Failed to fetch image batch', error)
      return []
    }
  }

  // 预加载图片文件
  async function prefetchImageFile(imageData) {
    if (prefetchedImages.value.has(imageData.id)) return

    try {
      const response = await fetch(`/api/images/${imageData.id}/file`)
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      prefetchedImages.value.set(imageData.id, url)
    } catch (error) {
      console.error('Failed to prefetch image', imageData.id, error)
    }
  }

  // 初始化预加载（首次加载，显示全屏进度）
  async function initializePrefetch(datasetId) {
    isInitialLoad.value = true
    isPrefetching.value = true
    prefetchProgress.value = 0

    const images = await fetchImageBatch(datasetId, PREFETCH_SIZE)
    if (images.length === 0) {
      isPrefetching.value = false
      isInitialLoad.value = false
      return null
    }

    imageQueue.value = images

    // 预加载所有图片文件
    for (let i = 0; i < images.length; i++) {
      await prefetchImageFile(images[i])
      prefetchProgress.value = Math.round(((i + 1) / images.length) * 100)
    }

    isPrefetching.value = false
    isInitialLoad.value = false

    // 返回第一张图片
    return getNextFromQueue()
  }

  // 从队列取出下一张图片
  function getNextFromQueue() {
    if (imageQueue.value.length === 0) return null

    const nextImage = imageQueue.value.shift()
    currentImage.value = nextImage
    annotations.value = nextImage.annotations || []
    saveHistory()

    return nextImage
  }

  // 后台预加载更多图片
  async function backgroundPrefetch(datasetId) {
    if (isPrefetching.value) return
    if (imageQueue.value.length >= PREFETCH_THRESHOLD) return

    isPrefetching.value = true
    prefetchProgress.value = 0

    const images = await fetchImageBatch(datasetId, PREFETCH_SIZE)

    // 过滤已在队列中的图片
    const existingIds = new Set(imageQueue.value.map(img => img.id))
    const newImages = images.filter(img => !existingIds.has(img.id))

    if (newImages.length > 0) {
      for (let i = 0; i < newImages.length; i++) {
        await prefetchImageFile(newImages[i])
        prefetchProgress.value = Math.round(((i + 1) / newImages.length) * 100)
      }
      imageQueue.value.push(...newImages)
    }

    isPrefetching.value = false
  }

  // 获取下一张图片（使用预加载队列）
  async function fetchNextImage(datasetId) {
    isLoading.value = true
    try {
      // 首次加载，初始化预加载队列
      if (imageQueue.value.length === 0 && !currentImage.value) {
        const result = await initializePrefetch(datasetId)
        return result
      }

      // 从队列取图片
      const nextImage = getNextFromQueue()

      // 检查是否需要后台预加载更多
      if (imageQueue.value.length < PREFETCH_THRESHOLD) {
        backgroundPrefetch(datasetId)
      }

      if (!nextImage) {
        // 队列空了，尝试直接获取
        const response = await api.get(`/images/next/${datasetId}`)
        if (response.data) {
          currentImage.value = response.data
          annotations.value = response.data.annotations || []
          saveHistory()
        } else {
          currentImage.value = null
          annotations.value = []
        }
      }

      return currentImage.value
    } finally {
      isLoading.value = false
    }
  }

  // 获取预加载的图片 URL
  function getPrefetchedImageUrl(imageId) {
    return prefetchedImages.value.get(imageId)
  }

  // 清理预加载缓存
  function clearPrefetchCache() {
    for (const url of prefetchedImages.value.values()) {
      URL.revokeObjectURL(url)
    }
    prefetchedImages.value.clear()
  }

  // 获取指定图片
  async function fetchImage(imageId) {
    isLoading.value = true
    try {
      const response = await api.get(`/images/${imageId}`)
      currentImage.value = response.data
      annotations.value = response.data.annotations || []
      saveHistory()
      return currentImage.value
    } finally {
      isLoading.value = false
    }
  }

  // 添加标注
  function addAnnotation(annotation) {
    const newAnnotation = {
      ...annotation,
      id: Date.now(), // 临时ID
      category_id: selectedCategory.value?.id || annotation.category_id
    }
    annotations.value.push(newAnnotation)
    saveHistory()
    return newAnnotation
  }

  // 更新标注
  function updateAnnotation(id, updates) {
    const index = annotations.value.findIndex(a => a.id === id)
    if (index !== -1) {
      annotations.value[index] = { ...annotations.value[index], ...updates }
      saveHistory()
    }
  }

  // 删除标注
  function removeAnnotation(id) {
    const index = annotations.value.findIndex(a => a.id === id)
    if (index !== -1) {
      annotations.value.splice(index, 1)
      saveHistory()
    }
  }

  // 保存历史记录
  function saveHistory() {
    // 如果在历史中间，删除后面的记录
    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1)
    }
    history.value.push(JSON.parse(JSON.stringify(annotations.value)))
    historyIndex.value = history.value.length - 1

    // 限制历史记录数量
    if (history.value.length > 50) {
      history.value.shift()
      historyIndex.value--
    }
  }

  // 撤销
  function undo() {
    if (canUndo.value) {
      historyIndex.value--
      annotations.value = JSON.parse(JSON.stringify(history.value[historyIndex.value]))
    }
  }

  // 重做
  function redo() {
    if (canRedo.value) {
      historyIndex.value++
      annotations.value = JSON.parse(JSON.stringify(history.value[historyIndex.value]))
    }
  }

  // 记录已处理图片到历史
  function recordToProcessedHistory(image, imageAnnotations) {
    // 如果正在浏览历史，先截断后面的部分
    if (isInHistory.value && historyPosition.value < processedHistory.value.length - 1) {
      processedHistory.value = processedHistory.value.slice(0, historyPosition.value + 1)
    }

    processedHistory.value.push({
      ...image,
      annotations: JSON.parse(JSON.stringify(imageAnnotations))
    })
    historyPosition.value = processedHistory.value.length - 1
    isInHistory.value = false

    // 限制历史记录数量
    if (processedHistory.value.length > 50) {
      processedHistory.value.shift()
      historyPosition.value--
    }
  }

  // 返回上一张
  async function goToPreviousImage() {
    if (!canGoPrevious.value) return null

    // 如果刚开始返回，当前图片也需要记录（如果还没记录）
    if (!isInHistory.value && currentImage.value) {
      // 当前图片入栈（但不再次推入如果已经在栈顶）
      const lastInHistory = processedHistory.value[processedHistory.value.length - 1]
      if (!lastInHistory || lastInHistory.id !== currentImage.value.id) {
        processedHistory.value.push({
          ...currentImage.value,
          annotations: JSON.parse(JSON.stringify(annotations.value))
        })
        historyPosition.value = processedHistory.value.length - 1
      }
    }

    isInHistory.value = true
    historyPosition.value--

    const prevImage = processedHistory.value[historyPosition.value]
    if (prevImage) {
      isLoading.value = true
      try {
        // 从后端获取最新状态
        const response = await api.get(`/images/${prevImage.id}`)
        currentImage.value = response.data
        annotations.value = response.data.annotations || []
        history.value = []
        historyIndex.value = -1
        saveHistory()
      } finally {
        isLoading.value = false
      }
    }

    return currentImage.value
  }

  // 前往下一张（在历史中导航）
  async function goToNextImage() {
    if (!canGoNext.value) return null

    historyPosition.value++
    const nextImage = processedHistory.value[historyPosition.value]

    if (nextImage) {
      isLoading.value = true
      try {
        const response = await api.get(`/images/${nextImage.id}`)
        currentImage.value = response.data
        annotations.value = response.data.annotations || []
        history.value = []
        historyIndex.value = -1
        saveHistory()
      } finally {
        isLoading.value = false
      }
    }

    // 如果到达历史末尾，退出历史模式
    if (historyPosition.value === processedHistory.value.length - 1) {
      isInHistory.value = false
    }

    return currentImage.value
  }

  // 退出历史模式，继续正常标注流程
  function exitHistoryMode() {
    isInHistory.value = false
    historyPosition.value = processedHistory.value.length - 1
  }

  // 保存标注
  async function saveAnnotations(skip = false) {
    if (!currentImage.value) return

    const annotationsData = annotations.value.map(a => ({
      category_id: a.category_id,
      x_center: a.x_center,
      y_center: a.y_center,
      width: a.width,
      height: a.height
    }))

    console.log('Saving annotations:', {
      imageId: currentImage.value.id,
      annotationsCount: annotationsData.length,
      isInHistory: isInHistory.value,
      skip
    })

    const response = await api.post(`/images/${currentImage.value.id}/save`, {
      annotations: annotationsData,
      skip
    })

    console.log('Save response:', response.data)

    // 记录到已处理历史（如果不在历史模式中）
    if (!isInHistory.value) {
      recordToProcessedHistory(currentImage.value, annotationsData)
    }

    // 返回保存的标注数量，便于调用者确认
    return annotationsData.length
  }

  // 根据快捷键选择类别
  function selectCategoryByKey(key) {
    const category = categories.value.find(c => c.shortcut_key === key)
    if (category) {
      selectedCategory.value = category
      return category
    }
    return null
  }

  // 清空状态
  function reset() {
    currentImage.value = null
    annotations.value = []
    history.value = []
    historyIndex.value = -1
    imageQueue.value = []
    isInitialLoad.value = true
    processedHistory.value = []
    historyPosition.value = -1
    isInHistory.value = false
    clearPrefetchCache()
  }

  return {
    currentImage,
    annotations,
    categories,
    selectedCategory,
    isLoading,
    canUndo,
    canRedo,
    // 预加载相关
    imageQueue,
    queueLength,
    prefetchProgress,
    isPrefetching,
    isInitialLoad,
    // 已处理历史相关
    processedHistory,
    isInHistory,
    canGoPrevious,
    canGoNext,
    // 方法
    loadCategories,
    fetchNextImage,
    fetchImage,
    addAnnotation,
    updateAnnotation,
    removeAnnotation,
    undo,
    redo,
    saveAnnotations,
    selectCategoryByKey,
    getPrefetchedImageUrl,
    goToPreviousImage,
    goToNextImage,
    exitHistoryMode,
    reset
  }
})
