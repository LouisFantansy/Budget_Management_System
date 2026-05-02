<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Database, Plus, Trash2 } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'
import type { MasterDataKind } from '../types/budget'

const store = useWorkbenchStore()

const tabs: Array<{ key: MasterDataKind; label: string }> = [
  { key: 'categories', label: 'Category' },
  { key: 'project-categories', label: 'Project Category' },
  { key: 'product-lines', label: 'Product Line' },
  { key: 'projects', label: 'Project' },
  { key: 'vendors', label: 'Vendor' },
  { key: 'regions', label: 'Region' },
  { key: 'cost-centers', label: 'Cost Center' },
  { key: 'gl-accounts', label: 'GL Account' },
]

const currentItems = computed(() => store.masterData[store.masterDataKind])

function projectCategoryValue(item: unknown) {
  if (typeof item !== 'object' || item === null || !('project_category' in item)) return ''
  return (item as { project_category: string | null }).project_category ?? ''
}

function productLineValue(item: unknown) {
  if (typeof item !== 'object' || item === null || !('product_line' in item)) return ''
  return (item as { product_line: string | null }).product_line ?? ''
}

function updateName(itemId: string, event: Event) {
  const target = event.target as HTMLInputElement
  store.updateMasterData(store.masterDataKind, itemId, { name: target.value.trim() })
}

function updateSortOrder(itemId: string, event: Event) {
  const target = event.target as HTMLInputElement
  store.updateMasterData(store.masterDataKind, itemId, { sort_order: Number(target.value || 0) })
}

function toggleActive(itemId: string, event: Event) {
  const target = event.target as HTMLInputElement
  store.updateMasterData(store.masterDataKind, itemId, { is_active: target.checked })
}

function updateProjectRelation(
  itemId: string,
  field: 'project_category' | 'product_line',
  event: Event,
) {
  const target = event.target as HTMLSelectElement
  store.updateMasterData('projects', itemId, { [field]: target.value || null })
}

function removeItem(itemId: string, name: string) {
  if (window.confirm(`确认删除主数据「${name}」？`)) {
    store.deleteMasterData(store.masterDataKind, itemId)
  }
}

onMounted(() => {
  store.loadMasterData()
})
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Master Data</p>
      <h1>主数据管理</h1>
    </div>
    <button class="primary-button" type="button" :disabled="store.actionLoading" @click="store.createMasterData">
      <Plus :size="17" />
      新增主数据
    </button>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="content-grid">
    <article class="panel wide-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Data Scope</p>
          <h2>数据列表</h2>
        </div>
        <Database :size="18" />
      </div>

      <div class="masterdata-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="context-pill"
          type="button"
          :class="{ active: store.masterDataKind === tab.key }"
          @click="store.masterDataKind = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="field-form masterdata-form" :class="{ 'masterdata-form-project': store.masterDataKind === 'projects' }">
        <input v-model="store.masterDataDraft.code" placeholder="编码，如 CLOUD" />
        <input v-model="store.masterDataDraft.name" placeholder="名称，如 Cloud Service" />
        <input v-model="store.masterDataDraft.legacyName" placeholder="历史名称 / legacy name" />
        <input v-model="store.masterDataDraft.aliases" placeholder="别名，逗号分隔" />
        <select v-if="store.masterDataKind === 'projects'" v-model="store.masterDataDraft.projectCategoryId">
          <option value="">选择 Project Category</option>
          <option v-for="item in store.masterData['project-categories']" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
        <select v-if="store.masterDataKind === 'projects'" v-model="store.masterDataDraft.productLineId">
          <option value="">选择 Product Line</option>
          <option v-for="item in store.masterData['product-lines']" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
        <select v-if="store.masterDataKind === 'cost-centers'" v-model="store.masterDataDraft.departmentId">
          <option value="">选择部门</option>
          <option v-for="item in store.departments" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
        <select v-if="store.masterDataKind === 'gl-accounts'" v-model="store.masterDataDraft.expenseType">
          <option value="">费用类型</option>
          <option value="opex">OPEX</option>
          <option value="capex">CAPEX</option>
        </select>
        <select v-if="store.masterDataKind === 'gl-accounts'" v-model="store.masterDataDraft.mappedCategoryId">
          <option value="">映射 Category</option>
          <option v-for="item in store.masterData.categories" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
        <select v-if="store.masterDataKind === 'gl-accounts'" v-model="store.masterDataDraft.mappedProjectCategoryId">
          <option value="">映射 Project Category</option>
          <option v-for="item in store.masterData['project-categories']" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
      </div>

      <div class="data-table">
        <div class="table-head table-row masterdata-row">
          <span>编码</span>
          <span>名称</span>
          <span v-if="store.masterDataKind === 'projects'">Project Category</span>
          <span v-if="store.masterDataKind === 'projects'">Product Line</span>
          <span>状态</span>
          <span>排序</span>
          <span>操作</span>
        </div>
        <div
          v-for="item in currentItems"
          :key="item.id"
          class="table-row masterdata-row"
          :class="{ 'masterdata-row-project': store.masterDataKind === 'projects' }"
        >
          <strong>{{ item.code }}</strong>
          <input class="masterdata-input" :value="item.name" :disabled="store.actionLoading" @change="updateName(item.id, $event)" />
          <select
            v-if="store.masterDataKind === 'projects'"
            class="masterdata-input"
            :value="projectCategoryValue(item)"
            :disabled="store.actionLoading"
            @change="updateProjectRelation(item.id, 'project_category', $event)"
          >
            <option value="">未设置</option>
            <option v-for="projectCategory in store.masterData['project-categories']" :key="projectCategory.id" :value="projectCategory.id">
              {{ projectCategory.name }}
            </option>
          </select>
          <select
            v-if="store.masterDataKind === 'projects'"
            class="masterdata-input"
            :value="productLineValue(item)"
            :disabled="store.actionLoading"
            @change="updateProjectRelation(item.id, 'product_line', $event)"
          >
            <option value="">未设置</option>
            <option v-for="productLine in store.masterData['product-lines']" :key="productLine.id" :value="productLine.id">
              {{ productLine.name }}
            </option>
          </select>
          <label class="field-required-toggle">
            <input :checked="item.is_active" type="checkbox" :disabled="store.actionLoading" @change="toggleActive(item.id, $event)" />
            {{ item.is_active ? '启用' : '停用' }}
          </label>
          <input class="masterdata-input short" :value="item.sort_order" type="number" :disabled="store.actionLoading" @change="updateSortOrder(item.id, $event)" />
          <button class="icon-button danger-icon" type="button" :disabled="store.actionLoading" @click="removeItem(item.id, item.name)">
            <Trash2 :size="15" />
          </button>
        </div>
      </div>
    </article>
  </section>
</template>
