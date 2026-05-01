<script setup lang="ts">
import { Copy, Eye, FunctionSquare, ListChecks } from 'lucide-vue-next'

const fields = ['预算编号', 'Category', 'Project', '预算条目描述', '单价', '1-12 月数量', '1-12 月金额']
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Schema Version 1</p>
      <h1>模板管理</h1>
    </div>
    <button class="primary-button" type="button">
      <Copy :size="17" />
      复制上一周期
    </button>
  </section>

  <section class="content-grid">
    <article class="panel wide-panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">OPEX Template</p>
          <h2>字段配置</h2>
        </div>
        <span class="status-chip">Active</span>
      </div>
      <div class="field-list">
        <div v-for="field in fields" :key="field">
          <ListChecks :size="16" />
          <span>{{ field }}</span>
          <em>进入审批快照</em>
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
      </div>
    </article>
  </section>
</template>
