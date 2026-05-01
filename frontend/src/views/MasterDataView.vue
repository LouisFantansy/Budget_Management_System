<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Database, Plus } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'
import type { MasterDataKind } from '../types/budget'

const store = useWorkbenchStore()

const tabs: Array<{ key: MasterDataKind; label: string }> = [
  { key: 'categories', label: 'Category' },
  { key: 'projects', label: 'Project' },
  { key: 'vendors', label: 'Vendor' },
  { key: 'regions', label: 'Region' },
]

const currentItems = computed(() => store.masterData[store.masterDataKind])

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
        </div>
        <div v-for="item in currentItems" :key="item.id" class="table-row masterdata-row">
          <strong>{{ item.code }}</strong>
          <span>{{ item.name }}</span>
          <span>{{ item.is_active ? '启用' : '停用' }}</span>
          <span>{{ item.sort_order }}</span>
        </div>
      </div>
    </article>
  </section>
</template>
