<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Bell, CheckCheck, Clock3, MessageSquareText } from 'lucide-vue-next'
import { useWorkbenchStore } from '../stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.loadNotifications()
})

const unreadNotifications = computed(() => store.notifications.filter((item) => item.status === 'unread'))

function categoryLabel(category: string) {
  if (category === 'approval_todo') return '审批待办'
  if (category === 'approval_result') return '审批结果'
  if (category === 'anomaly_alert') return '异常提醒'
  return '系统通知'
}
</script>

<template>
  <section class="page-head">
    <div>
      <p class="eyebrow">Notification Center</p>
      <h1>通知中心</h1>
    </div>
    <div class="button-group">
      <span class="context-badge">未读 {{ store.notificationSummary.unread_count }}</span>
      <button class="secondary-button" type="button" :disabled="store.actionLoading || !unreadNotifications.length" @click="store.markNotificationsRead()">
        <CheckCheck :size="17" />
        全部标记已读
      </button>
    </div>
  </section>

  <p v-if="store.error" class="error-banner">{{ store.error }}</p>

  <section class="content-grid">
    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Summary</p>
          <h2>通知概览</h2>
        </div>
        <Bell :size="18" />
      </div>
      <div class="detail-grid">
        <div class="detail-card">
          <span>通知总数</span>
          <strong>{{ store.notificationSummary.total }}</strong>
        </div>
        <div class="detail-card">
          <span>未读数</span>
          <strong>{{ store.notificationSummary.unread_count }}</strong>
        </div>
        <div class="detail-card">
          <span>最近未读</span>
          <strong>{{ store.notificationSummary.latest_unread_title || '-' }}</strong>
        </div>
        <div class="detail-card">
          <span>当前状态</span>
          <strong>{{ unreadNotifications.length ? '有待处理通知' : '已清空' }}</strong>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="panel-title">
        <div>
          <p class="eyebrow">Inbox</p>
          <h2>通知列表</h2>
        </div>
        <Clock3 :size="18" />
      </div>

      <div v-if="store.notifications.length" class="notification-list">
        <div v-for="item in store.notifications" :key="item.id" class="notification-item" :class="{ unread: item.status === 'unread' }">
          <div class="notification-copy">
            <div class="notification-head">
              <span class="status-chip">{{ categoryLabel(item.category) }}</span>
              <span class="notification-time">{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span>
            </div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.message || '无附加说明' }}</p>
          </div>
          <button
            v-if="item.status === 'unread'"
            class="text-button"
            type="button"
            :disabled="store.actionLoading"
            @click="store.markNotificationsRead([item.id])"
          >
            标记已读
          </button>
          <span v-else class="context-badge">
            <MessageSquareText :size="15" />
            已读
          </span>
        </div>
      </div>
      <p v-else class="empty-note">当前没有通知。</p>
    </article>
  </section>
</template>
