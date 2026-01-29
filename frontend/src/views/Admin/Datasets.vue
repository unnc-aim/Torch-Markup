<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../utils/api'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const userStore = useUserStore()

const datasets = ref([])
const loading = ref(true)
const dialogVisible = ref(false)
const dialogTitle = ref('创建数据集')
const isEdit = ref(false)

const form = ref({
  id: null,
  name: '',
  description: '',
  image_path: '',
  label_path: ''
})

// 批量导入相关
const batchImportVisible = ref(false)
const batchImportForm = ref({
  root_path: ''
})
const batchImportProgress = ref({
  status: '',
  message: '',
  total_folders: 0,
  processed_folders: 0,
  datasets_created: 0,
  total_images_imported: 0,
  current_folder: ''
})
const isImporting = ref(false)

onMounted(() => {
  loadDatasets()
})

async function loadDatasets() {
  loading.value = true
  try {
    const response = await api.get('/datasets')
    datasets.value = response.data
  } finally {
    loading.value = false
  }
}

function showCreateDialog() {
  isEdit.value = false
  dialogTitle.value = '创建数据集'
  form.value = {
    id: null,
    name: '',
    description: '',
    image_path: '',
    label_path: ''
  }
  dialogVisible.value = true
}

function showEditDialog(dataset) {
  isEdit.value = true
  dialogTitle.value = '编辑数据集'
  form.value = { ...dataset }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.value.name || !form.value.image_path) {
    ElMessage.warning('请填写必填字段')
    return
  }

  try {
    if (isEdit.value) {
      await api.put(`/datasets/${form.value.id}`, form.value)
      ElMessage.success('更新成功')
    } else {
      await api.post('/datasets', form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadDatasets()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

async function handleScan(dataset) {
  try {
    const response = await api.post(`/datasets/${dataset.id}/scan`)
    ElMessage.success(`扫描完成: 发现${response.data.found_images}张图片, 导入${response.data.imported_images}张, 跳过${response.data.skipped_images}张`)
    loadDatasets()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

async function handleDelete(dataset) {
  try {
    await ElMessageBox.confirm(
      `确定要删除数据集 "${dataset.name}" 吗？这将删除所有相关的图片和标注数据。`,
      '警告',
      { type: 'warning' }
    )

    await api.delete(`/datasets/${dataset.id}`)
    ElMessage.success('删除成功')
    loadDatasets()
  } catch (error) {
    if (error !== 'cancel') {
      // 错误已在拦截器中处理
    }
  }
}

function goToCategories(datasetId) {
  router.push(`/admin/categories/${datasetId}`)
}

function showBatchImportDialog() {
  batchImportForm.value = {
    root_path: ''
  }
  batchImportProgress.value = {
    status: '',
    message: '',
    total_folders: 0,
    processed_folders: 0,
    datasets_created: 0,
    total_images_imported: 0,
    current_folder: ''
  }
  isImporting.value = false
  batchImportVisible.value = true
}

async function startBatchImport() {
  if (!batchImportForm.value.root_path) {
    ElMessage.warning('请填写根目录路径')
    return
  }

  isImporting.value = true
  batchImportProgress.value = {
    status: 'scanning',
    message: '正在扫描目录...',
    total_folders: 0,
    processed_folders: 0,
    datasets_created: 0,
    total_images_imported: 0,
    current_folder: ''
  }

  try {
    const token = userStore.token
    const response = await fetch('/api/datasets/batch-import', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(batchImportForm.value)
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || '导入失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      const lines = text.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            batchImportProgress.value = { ...batchImportProgress.value, ...data }

            if (data.status === 'done') {
              ElMessage.success(data.message)
              loadDatasets()
            } else if (data.status === 'error') {
              ElMessage.error(data.message)
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  } catch (error) {
    ElMessage.error(error.message || '批量导入失败')
  } finally {
    isImporting.value = false
  }
}

function closeBatchImportDialog() {
  if (isImporting.value) {
    ElMessage.warning('正在导入中，请等待完成')
    return
  }
  batchImportVisible.value = false
}
</script>

<template>
  <div class="datasets-page">
    <div class="page-header">
      <h2>数据集管理</h2>
      <div class="header-buttons">
        <el-button @click="showBatchImportDialog">
          批量导入
        </el-button>
        <el-button type="primary" @click="showCreateDialog">
          创建数据集
        </el-button>
      </div>
    </div>

    <el-table :data="datasets" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column prop="image_path" label="图片路径" show-overflow-tooltip />
      <el-table-column prop="total_images" label="图片数" width="100" />
      <el-table-column prop="labeled_images" label="已标注" width="100" />
      <el-table-column label="进度" width="120">
        <template #default="{ row }">
          <el-progress
            :percentage="row.total_images > 0 ? Math.round(row.labeled_images / row.total_images * 100) : 0"
            :stroke-width="6"
          />
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="goToCategories(row.id)">类别</el-button>
          <el-button size="small" type="primary" @click="handleScan(row)">扫描</el-button>
          <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="数据集名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="数据集描述" />
        </el-form-item>
        <el-form-item label="图片路径" required>
          <el-input v-model="form.image_path" placeholder="/path/to/images" />
          <div class="form-tip">服务器上的图片目录绝对路径</div>
        </el-form-item>
        <el-form-item label="标签路径">
          <el-input v-model="form.label_path" placeholder="/path/to/labels" />
          <div class="form-tip">YOLO标签保存目录（可选）</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog
      v-model="batchImportVisible"
      title="批量导入数据集"
      width="550px"
      :close-on-click-modal="!isImporting"
      :close-on-press-escape="!isImporting"
      :show-close="!isImporting"
      @close="closeBatchImportDialog"
    >
      <el-form :model="batchImportForm" label-width="100px" :disabled="isImporting">
        <el-form-item label="根目录" required>
          <el-input v-model="batchImportForm.root_path" placeholder="/path/to/datasets" />
          <div class="form-tip">递归扫描所有 image/images 文件夹，labels 自动创建在同级目录</div>
        </el-form-item>
      </el-form>

      <!-- 进度显示 -->
      <div v-if="batchImportProgress.status" class="import-progress">
        <el-divider />
        <div class="progress-info">
          <div class="progress-status">
            <el-icon v-if="batchImportProgress.status === 'scanning' || batchImportProgress.status === 'importing'" class="is-loading">
              <i class="el-icon-loading"></i>
            </el-icon>
            <el-tag v-if="batchImportProgress.status === 'done'" type="success">完成</el-tag>
            <el-tag v-else-if="batchImportProgress.status === 'error'" type="danger">错误</el-tag>
            <el-tag v-else type="info">{{ batchImportProgress.status === 'scanning' ? '扫描中' : '导入中' }}</el-tag>
          </div>
          <div class="progress-message">{{ batchImportProgress.message }}</div>
        </div>

        <div v-if="batchImportProgress.total_folders > 0" class="progress-detail">
          <el-progress
            :percentage="Math.round(batchImportProgress.processed_folders / batchImportProgress.total_folders * 100)"
            :status="batchImportProgress.status === 'done' ? 'success' : batchImportProgress.status === 'error' ? 'exception' : ''"
          />
          <div class="progress-stats">
            <span>文件夹: {{ batchImportProgress.processed_folders }} / {{ batchImportProgress.total_folders }}</span>
            <span>创建数据集: {{ batchImportProgress.datasets_created }}</span>
            <span>导入图片: {{ batchImportProgress.total_images_imported }}</span>
          </div>
        </div>

        <div v-if="batchImportProgress.current_folder && batchImportProgress.status === 'importing'" class="current-folder">
          当前: {{ batchImportProgress.current_folder }}
        </div>
      </div>

      <template #footer>
        <el-button @click="closeBatchImportDialog" :disabled="isImporting">
          {{ batchImportProgress.status === 'done' ? '关闭' : '取消' }}
        </el-button>
        <el-button
          type="primary"
          @click="startBatchImport"
          :loading="isImporting"
          :disabled="batchImportProgress.status === 'done'"
        >
          {{ isImporting ? '导入中...' : '开始导入' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.datasets-page {
  background: white;
  padding: 24px;
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
}

.header-buttons {
  display: flex;
  gap: 12px;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.import-progress {
  margin-top: 16px;
}

.progress-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.progress-status {
  flex-shrink: 0;
}

.progress-message {
  color: #606266;
  font-size: 14px;
}

.progress-detail {
  margin-bottom: 12px;
}

.progress-stats {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 13px;
  color: #909399;
}

.current-folder {
  font-size: 12px;
  color: #909399;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.is-loading {
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
