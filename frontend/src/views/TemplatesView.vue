<script setup lang="ts">
import { onMounted } from 'vue'
import { Copy, Eye, FunctionSquare, ListChecks, Plus } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.loadTemplates()
})
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Schema Version 1</p>
      <h1>模板管理</h1>
    </div>
    <button class="primary-button" type="button" :disabled="store.actionLoading" @click="store.createTemplateField">
      <Plus :size="17" />
      新增字段
    </button>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="content-grid">
    <article class="panel wide-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">{{ store.templates[0]?.name ?? 'Template' }}</p>
          <h2>字段配置</h2>
        </div>
        <span class="status-chip">{{ store.templates[0]?.status ?? 'Loading' }}</span>
      </div>
      <div class="field-list">
        <div v-for="field in store.templateFields" :key="field.id">
          <ListChecks :size="16" />
          <span>{{ field.label }}</span>
          <em>{{ field.code }} · {{ field.data_type }} · {{ field.required ? '必填' : '选填' }}</em>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Rules</p>
          <h2>公式与权限</h2>
        </div>
        <FunctionSquare :size="18" />
      </div>
      <div class="rule-stack">
        <p>总数量 = 1-12 月数量加总</p>
        <p>总金额 = 1-12 月金额加总</p>
        <p><Eye :size="15" />保密列仅一级预算管理员可见</p>
        <p><Copy :size="15" />Schema Version {{ store.templates[0]?.schema_version ?? '-' }}</p>
      </div>
    </article>
  </section>
</template>
