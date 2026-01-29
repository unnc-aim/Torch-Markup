<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'

const props = defineProps({
  imageId: Number,
  annotations: Array,
  categories: Array,
  selectedCategory: Object,
  mode: {
    type: String,
    default: 'annotate'  // 'annotate' | 'pan'
  }
})

const emit = defineEmits(['add', 'update', 'delete', 'zoom-change'])

const canvasRef = ref(null)
const containerRef = ref(null)
const ctx = ref(null)
const image = ref(null)

// 画布状态
const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)

// 绘制状态
const isDrawing = ref(false)
const isDragging = ref(false)
const isPanning = ref(false)
const spacePressed = ref(false)

const startPoint = ref({ x: 0, y: 0 })
const currentBox = ref(null)
const selectedAnnotation = ref(null)
const dragHandle = ref(null)

// 拖动调整时的临时边界框（用于实时预览）
const dragBox = ref(null)

// 图片URL
const imageUrl = computed(() => `/api/images/${props.imageId}/file`)

onMounted(() => {
  const canvas = canvasRef.value
  ctx.value = canvas.getContext('2d')
  loadImage()

  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
})

watch(() => props.imageId, () => {
  resetView()
  loadImage()
})

watch(() => props.annotations, () => {
  draw()
}, { deep: true })

// 模式变化时更新光标
watch(() => props.mode, () => {
  if (canvasRef.value) {
    if (props.mode === 'pan') {
      canvasRef.value.style.cursor = 'grab'
    } else {
      canvasRef.value.style.cursor = 'crosshair'
    }
  }
})

function loadImage() {
  if (!props.imageId) return

  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    image.value = img
    fitToContainer()
    draw()
  }
  img.src = imageUrl.value
}

function fitToContainer() {
  if (!image.value || !containerRef.value) return

  const container = containerRef.value
  const img = image.value

  // 计算适合容器的缩放比例
  const scaleX = container.clientWidth / img.width
  const scaleY = container.clientHeight / img.height
  scale.value = Math.min(scaleX, scaleY) * 0.9

  // 居中
  offsetX.value = (container.clientWidth - img.width * scale.value) / 2
  offsetY.value = (container.clientHeight - img.height * scale.value) / 2

  resizeCanvas()
}

function resizeCanvas() {
  if (!containerRef.value) return
  canvasRef.value.width = containerRef.value.clientWidth
  canvasRef.value.height = containerRef.value.clientHeight
  draw()
}

function resetView() {
  scale.value = 1
  offsetX.value = 0
  offsetY.value = 0
  selectedAnnotation.value = null
}

function draw() {
  if (!ctx.value || !canvasRef.value) return

  const canvas = canvasRef.value
  ctx.value.clearRect(0, 0, canvas.width, canvas.height)

  // 绘制图片
  if (image.value) {
    ctx.value.save()
    ctx.value.translate(offsetX.value, offsetY.value)
    ctx.value.scale(scale.value, scale.value)
    ctx.value.drawImage(image.value, 0, 0)
    ctx.value.restore()
  }

  // 绘制已有标注
  props.annotations.forEach((ann, index) => {
    const isSelected = ann.id === selectedAnnotation.value?.id
    // 如果正在拖动调整这个标注，使用 dragBox 绘制
    if (isSelected && isDragging.value && dragBox.value) {
      drawAnnotationWithBox(ann, dragBox.value, index, true)
    } else {
      drawAnnotation(ann, index, isSelected)
    }
  })

  // 绘制当前正在绘制的框
  if (currentBox.value) {
    drawBox(currentBox.value, props.selectedCategory?.color || '#FF0000', true)
  }
}

function drawAnnotation(ann, index, isSelected) {
  const category = props.categories.find(c => c.id === ann.category_id)
  const color = category?.color || '#FF0000'

  // 将YOLO格式转换为像素坐标
  const imgW = image.value.width
  const imgH = image.value.height

  const x = (ann.x_center - ann.width / 2) * imgW
  const y = (ann.y_center - ann.height / 2) * imgH
  const w = ann.width * imgW
  const h = ann.height * imgH

  const box = { x, y, w, h }
  drawBox(box, color, isSelected)

  // 绘制类别标签和编号
  const screenX = x * scale.value + offsetX.value
  const screenY = y * scale.value + offsetY.value

  const labelText = `#${index + 1} ${category?.name || ''}`
  ctx.value.font = '12px Arial'
  ctx.value.fillStyle = color
  ctx.value.fillRect(screenX, screenY - 18, ctx.value.measureText(labelText).width + 8, 18)
  ctx.value.fillStyle = 'white'
  ctx.value.fillText(labelText, screenX + 4, screenY - 5)
}

function drawAnnotationWithBox(ann, box, index, isSelected) {
  const category = props.categories.find(c => c.id === ann.category_id)
  const color = category?.color || '#FF0000'

  drawBox(box, color, isSelected)

  // 绘制类别标签和编号
  const screenX = box.x * scale.value + offsetX.value
  const screenY = box.y * scale.value + offsetY.value

  const labelText = `#${index + 1} ${category?.name || ''}`
  ctx.value.font = '12px Arial'
  ctx.value.fillStyle = color
  ctx.value.fillRect(screenX, screenY - 18, ctx.value.measureText(labelText).width + 8, 18)
  ctx.value.fillStyle = 'white'
  ctx.value.fillText(labelText, screenX + 4, screenY - 5)
}

function drawBox(box, color, isSelected) {
  const screenX = box.x * scale.value + offsetX.value
  const screenY = box.y * scale.value + offsetY.value
  const screenW = box.w * scale.value
  const screenH = box.h * scale.value

  ctx.value.strokeStyle = color
  ctx.value.lineWidth = isSelected ? 3 : 2
  ctx.value.strokeRect(screenX, screenY, screenW, screenH)

  // 半透明填充
  ctx.value.fillStyle = color + '20'
  ctx.value.fillRect(screenX, screenY, screenW, screenH)

  // 选中时绘制调整手柄
  if (isSelected) {
    const handles = getHandles(screenX, screenY, screenW, screenH)
    ctx.value.fillStyle = color
    handles.forEach(h => {
      ctx.value.fillRect(h.x - 4, h.y - 4, 8, 8)
    })
  }
}

function getHandles(x, y, w, h) {
  return [
    { x: x, y: y, cursor: 'nw-resize', type: 'tl' },
    { x: x + w / 2, y: y, cursor: 'n-resize', type: 't' },
    { x: x + w, y: y, cursor: 'ne-resize', type: 'tr' },
    { x: x + w, y: y + h / 2, cursor: 'e-resize', type: 'r' },
    { x: x + w, y: y + h, cursor: 'se-resize', type: 'br' },
    { x: x + w / 2, y: y + h, cursor: 's-resize', type: 'b' },
    { x: x, y: y + h, cursor: 'sw-resize', type: 'bl' },
    { x: x, y: y + h / 2, cursor: 'w-resize', type: 'l' }
  ]
}

function screenToImage(screenX, screenY) {
  return {
    x: (screenX - offsetX.value) / scale.value,
    y: (screenY - offsetY.value) / scale.value
  }
}

function handleMouseDown(e) {
  // 阻止默认行为（Safari 拖动兼容性）
  e.preventDefault()

  const rect = canvasRef.value.getBoundingClientRect()
  const screenX = e.clientX - rect.left
  const screenY = e.clientY - rect.top

  // 拖动模式或空格键按下时进入平移模式
  if (props.mode === 'pan' || spacePressed.value) {
    isPanning.value = true
    startPoint.value = { x: e.clientX, y: e.clientY }
    canvasRef.value.style.cursor = 'grabbing'
    return
  }

  // 检查是否点击了调整手柄
  if (selectedAnnotation.value) {
    const handle = getClickedHandle(screenX, screenY)
    if (handle) {
      dragHandle.value = handle
      isDragging.value = true
      startPoint.value = screenToImage(screenX, screenY)
      // 初始化 dragBox 为当前标注的像素坐标
      const ann = selectedAnnotation.value
      const imgW = image.value.width
      const imgH = image.value.height
      dragBox.value = {
        x: (ann.x_center - ann.width / 2) * imgW,
        y: (ann.y_center - ann.height / 2) * imgH,
        w: ann.width * imgW,
        h: ann.height * imgH
      }
      return
    }
  }

  // 检查是否点击了已有标注
  const clickedAnn = getAnnotationAt(screenX, screenY)
  if (clickedAnn) {
    selectedAnnotation.value = clickedAnn
    draw()
    return
  }

  // 开始绘制新框
  if (props.selectedCategory) {
    selectedAnnotation.value = null
    isDrawing.value = true
    const imgPoint = screenToImage(screenX, screenY)
    startPoint.value = imgPoint
    currentBox.value = { x: imgPoint.x, y: imgPoint.y, w: 0, h: 0 }
  }
}

function handleMouseMove(e) {
  const rect = canvasRef.value.getBoundingClientRect()
  const screenX = e.clientX - rect.left
  const screenY = e.clientY - rect.top

  // 平移
  if (isPanning.value) {
    offsetX.value += e.clientX - startPoint.value.x
    offsetY.value += e.clientY - startPoint.value.y
    startPoint.value = { x: e.clientX, y: e.clientY }
    draw()
    return
  }

  // 调整大小
  if (isDragging.value && selectedAnnotation.value && dragHandle.value && dragBox.value) {
    const imgPoint = screenToImage(screenX, screenY)
    updateDragBox(dragHandle.value.type, imgPoint)
    draw()
    return
  }

  // 绘制中
  if (isDrawing.value && currentBox.value) {
    const imgPoint = screenToImage(screenX, screenY)
    currentBox.value.w = imgPoint.x - startPoint.value.x
    currentBox.value.h = imgPoint.y - startPoint.value.y
    draw()
  }

  // 更新光标
  updateCursor(screenX, screenY)
}

function handleMouseUp(e) {
  if (isPanning.value) {
    isPanning.value = false
    return
  }

  if (isDragging.value) {
    isDragging.value = false
    dragHandle.value = null
    // 保存更新
    if (selectedAnnotation.value && dragBox.value && image.value) {
      const imgW = image.value.width
      const imgH = image.value.height
      const box = dragBox.value
      emit('update', selectedAnnotation.value.id, {
        x_center: (box.x + box.w / 2) / imgW,
        y_center: (box.y + box.h / 2) / imgH,
        width: box.w / imgW,
        height: box.h / imgH
      })
    }
    dragBox.value = null
    return
  }

  if (isDrawing.value && currentBox.value) {
    isDrawing.value = false

    // 规范化框坐标
    let { x, y, w, h } = currentBox.value
    if (w < 0) { x += w; w = -w }
    if (h < 0) { y += h; h = -h }

    // 最小尺寸检查
    if (w > 5 && h > 5 && image.value) {
      // 转换为YOLO格式
      const imgW = image.value.width
      const imgH = image.value.height

      const annotation = {
        category_id: props.selectedCategory.id,
        x_center: (x + w / 2) / imgW,
        y_center: (y + h / 2) / imgH,
        width: w / imgW,
        height: h / imgH
      }

      emit('add', annotation)
    }

    currentBox.value = null
    draw()
  }
}

function handleWheel(e) {
  e.preventDefault()

  const rect = canvasRef.value.getBoundingClientRect()
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top

  const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1
  const newScale = Math.min(Math.max(scale.value * zoomFactor, 0.1), 10)

  // 以鼠标位置为中心缩放
  const imgPoint = screenToImage(mouseX, mouseY)
  scale.value = newScale
  offsetX.value = mouseX - imgPoint.x * newScale
  offsetY.value = mouseY - imgPoint.y * newScale

  emit('zoom-change', scale.value)
  draw()
}

function handleKeyDown(e) {
  if (e.code === 'Space') {
    spacePressed.value = true
    canvasRef.value.style.cursor = 'grab'
  }

  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedAnnotation.value) {
      emit('delete', selectedAnnotation.value.id)
      selectedAnnotation.value = null
      draw()
    }
  }
}

function handleKeyUp(e) {
  if (e.code === 'Space') {
    spacePressed.value = false
    canvasRef.value.style.cursor = 'crosshair'
  }
}

function getAnnotationAt(screenX, screenY) {
  if (!image.value) return null

  const imgPoint = screenToImage(screenX, screenY)
  const imgW = image.value.width
  const imgH = image.value.height

  for (let i = props.annotations.length - 1; i >= 0; i--) {
    const ann = props.annotations[i]
    const x = (ann.x_center - ann.width / 2) * imgW
    const y = (ann.y_center - ann.height / 2) * imgH
    const w = ann.width * imgW
    const h = ann.height * imgH

    if (imgPoint.x >= x && imgPoint.x <= x + w &&
        imgPoint.y >= y && imgPoint.y <= y + h) {
      return ann
    }
  }
  return null
}

function getClickedHandle(screenX, screenY) {
  if (!selectedAnnotation.value || !image.value) return null

  const ann = selectedAnnotation.value
  const imgW = image.value.width
  const imgH = image.value.height

  const x = (ann.x_center - ann.width / 2) * imgW
  const y = (ann.y_center - ann.height / 2) * imgH
  const w = ann.width * imgW
  const h = ann.height * imgH

  const handles = getHandles(
    x * scale.value + offsetX.value,
    y * scale.value + offsetY.value,
    w * scale.value,
    h * scale.value
  )

  for (const handle of handles) {
    if (Math.abs(screenX - handle.x) < 8 && Math.abs(screenY - handle.y) < 8) {
      return handle
    }
  }
  return null
}

function updateDragBox(handleType, imgPoint) {
  if (!dragBox.value) return

  let x1 = dragBox.value.x
  let y1 = dragBox.value.y
  let x2 = dragBox.value.x + dragBox.value.w
  let y2 = dragBox.value.y + dragBox.value.h

  switch (handleType) {
    case 'tl': x1 = imgPoint.x; y1 = imgPoint.y; break
    case 't': y1 = imgPoint.y; break
    case 'tr': x2 = imgPoint.x; y1 = imgPoint.y; break
    case 'r': x2 = imgPoint.x; break
    case 'br': x2 = imgPoint.x; y2 = imgPoint.y; break
    case 'b': y2 = imgPoint.y; break
    case 'bl': x1 = imgPoint.x; y2 = imgPoint.y; break
    case 'l': x1 = imgPoint.x; break
  }

  // 确保最小尺寸
  if (x2 - x1 < 10) x2 = x1 + 10
  if (y2 - y1 < 10) y2 = y1 + 10

  dragBox.value = {
    x: x1,
    y: y1,
    w: x2 - x1,
    h: y2 - y1
  }
}

function updateCursor(screenX, screenY) {
  // 拖动模式
  if (props.mode === 'pan') {
    canvasRef.value.style.cursor = isPanning.value ? 'grabbing' : 'grab'
    return
  }

  if (spacePressed.value) {
    canvasRef.value.style.cursor = isPanning.value ? 'grabbing' : 'grab'
    return
  }

  if (selectedAnnotation.value) {
    const handle = getClickedHandle(screenX, screenY)
    if (handle) {
      canvasRef.value.style.cursor = handle.cursor
      return
    }
  }

  const ann = getAnnotationAt(screenX, screenY)
  canvasRef.value.style.cursor = ann ? 'move' : 'crosshair'
}

// 暴露方法供外部调用
defineExpose({
  fitToContainer,
  scale
})
</script>

<template>
  <div ref="containerRef" class="canvas-wrapper">
    <canvas
      ref="canvasRef"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
      @wheel="handleWheel"
    />
  </div>
</template>

<style scoped>
.canvas-wrapper {
  width: 100%;
  height: 100%;
  overflow: hidden;
}

canvas {
  display: block;
  cursor: crosshair;
}
</style>
