<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../utils/api'

const route = useRoute()
const router = useRouter()

const datasetId = computed(() => parseInt(route.params.datasetId))
const dataset = ref(null)
const categories = ref([])
const allDatasets = ref([])
const loading = ref(true)
const dialogVisible = ref(false)
const isEdit = ref(false)
const importDialogVisible = ref(false)
const selectedSourceDataset = ref(null)

const colorOptions = [
  '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF',
  '#FF8000', '#8000FF', '#0080FF', '#FF0080', '#80FF00', '#00FF80'
]

const form = ref({
  id: null,
  dataset_id: datasetId.value,
  name: '',
  shortcut_key: '',
  color: '#FF0000',
  sort_order: 0
})

onMounted(async () => {
  await loadData()
})

async function loadData() {
  loading.value = true
  try {
    const [datasetRes, categoriesRes, datasetsRes] = await Promise.all([
      api.get(`/datasets/${datasetId.value}`),
      api.get(`/categories/dataset/${datasetId.value}`),
      api.get('/datasets')
    ])
    dataset.value = datasetRes.data
    categories.value = categoriesRes.data
    // 过滤掉当前数据集
    allDatasets.value = datasetsRes.data.filter(d => d.id !== datasetId.value)
  } finally {
    loading.value = false
  }
}

function showCreateDialog() {
  isEdit.value = false
  form.value = {
    id: null,
    dataset_id: datasetId.value,
    name: '',
    shortcut_key: '',
    color: colorOptions[categories.value.length % colorOptions.length],
    sort_order: categories.value.length
  }
  dialogVisible.value = true
}

function showEditDialog(category) {
  isEdit.value = true
  form.value = { ...category }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.value.name) {
    ElMessage.warning('请填写类别名称')
    return
  }

  try {
    if (isEdit.value) {
      await api.put(`/categories/${form.value.id}`, form.value)
      ElMessage.success('更新成功')
    } else {
      await api.post('/categories', form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

async function handleDelete(category) {
  try {
    await ElMessageBox.confirm(
      `确定要删除类别 "${category.name}" 吗？相关的标注将被清除。`,
      '警告',
      { type: 'warning' }
    )

    await api.delete(`/categories/${category.id}`)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      // 错误已在拦截器中处理
    }
  }
}

function showImportDialog() {
  selectedSourceDataset.value = null
  importDialogVisible.value = true
}

async function handleImportFromDataset() {
  if (!selectedSourceDataset.value) {
    ElMessage.warning('请选择源数据集')
    return
  }

  try {
    const response = await api.post(`/categories/import-from-dataset/${datasetId.value}`, {
      source_dataset_id: selectedSourceDataset.value
    })
    ElMessage.success(response.data.message)
    importDialogVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  }
}

async function handleImportFromConfig() {
  try {
    const response = await api.post(`/dataset-configs/${datasetId.value}/import-default-categories`)
    ElMessage.success(response.data.message)
    loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  }
}

function handleImportCommand(command) {
  if (command === 'dataset') {
    showImportDialog()
  } else if (command === 'config') {
    handleImportFromConfig()
  }
}
</script>

<template>
  <div class="categories-page" v-loading="loading">
    <div class="page-header">
      <div class="header-left">
        <el-button @click="router.push('/admin/datasets')" :icon="'ArrowLeft'">返回</el-button>
        <h2 v-if="dataset">{{ dataset.name }} - 类别管理</h2>
      </div>
      <div class="header-buttons">
        <el-dropdown @command="handleImportCommand" trigger="click">
          <el-button>
            导入类别 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="dataset">从其他数据集导入</el-dropdown-item>
              <el-dropdown-item command="config">从格式配置导入</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" @click="showCreateDialog" :icon="'Plus'">
          添加类别
        </el-button>
      </div>
    </div>

    <div class="categories-grid">
      <div
        v-for="category in categories"
        :key="category.id"
        class="category-card"
      >
        <div class="color-bar" :style="{ background: category.color }"></div>
        <div class="card-content">
          <h3>{{ category.name }}</h3>
          <div class="meta">
            <span v-if="category.shortcut_key" class="shortcut">
              快捷键: <kbd>{{ category.shortcut_key }}</kbd>
            </span>
            <span class="order">排序: {{ category.sort_order }}</span>
          </div>
          <div class="actions">
            <el-button size="small" @click="showEditDialog(category)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(category)">删除</el-button>
          </div>
        </div>
      </div>

      <div v-if="categories.length === 0" class="empty-card" @click="showCreateDialog">
        <el-icon :size="32"><Plus /></el-icon>
        <span>添加第一个类别</span>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑类别' : '添加类别'" width="400px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="类别名称" />
        </el-form-item>
        <el-form-item label="快捷键">
          <el-input
            v-model="form.shortcut_key"
            placeholder="如: 1, a, q"
            maxlength="1"
            style="width: 100px"
          />
          <div class="form-tip">用于快速选择类别的键盘快捷键</div>
        </el-form-item>
        <el-form-item label="颜色">
          <div class="color-picker">
            <div
              v-for="color in colorOptions"
              :key="color"
              class="color-option"
              :class="{ active: form.color === color }"
              :style="{ background: color }"
              @click="form.color = color"
            />
          </div>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 从数据集导入对话框 -->
    <el-dialog v-model="importDialogVisible" title="从其他数据集导入类别" width="400px">
      <el-form label-width="100px">
        <el-form-item label="源数据集">
          <el-select v-model="selectedSourceDataset" placeholder="选择数据集" style="width: 100%">
            <el-option
              v-for="ds in allDatasets"
              :key="ds.id"
              :value="ds.id"
              :label="ds.name"
            />
          </el-select>
        </el-form-item>
        <div class="form-tip" style="margin-left: 100px">
          已存在的类别名称将被跳过
        </div>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleImportFromDataset">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.categories-page {
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

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  margin: 0;
}

.header-buttons {
  display: flex;
  gap: 12px;
}

.categories-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
}

.category-card {
  border: 1px solid #eee;
  border-radius: 8px;
  overflow: hidden;
}

.color-bar {
  height: 8px;
}

.card-content {
  padding: 16px;
}

.card-content h3 {
  margin: 0 0 12px 0;
}

.meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  color: #666;
  font-size: 13px;
}

.meta kbd {
  padding: 2px 6px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 8px;
}

.empty-card {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #999;
  cursor: pointer;
  transition: all 0.2s;
}

.empty-card:hover {
  border-color: #409eff;
  color: #409eff;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.color-picker {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.color-option {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.color-option:hover {
  transform: scale(1.1);
}

.color-option.active {
  border-color: #333;
}
</style>
