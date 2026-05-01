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
]

const currentItems = computed(() => store.masterData[store.masterDataKind])

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

      <div class="field-form masterdata-form">
        <input v-model="store.masterDataDraft.code" placeholder="编码，如 CLOUD" />
        <input v-model="store.masterDataDraft.name" placeholder="名称，如 Cloud Service" />
      </div>

      <div class="data-table">
        <div class="table-head table-row masterdata-row">
          <span>编码</span>
          <span>名称</span>
          <span>状态</span>
          <span>排序</span>
          <span>操作</span>
        </div>
        <div v-for="item in currentItems" :key="item.id" class="table-row masterdata-row">
          <strong>{{ item.code }}</strong>
          <input class="masterdata-input" :value="item.name" :disabled="store.actionLoading" @change="updateName(item.id, $event)" />
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
