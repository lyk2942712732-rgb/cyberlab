<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ status: string }>()
const labels: Record<string, string> = { DRAFT: '草稿', PUBLISHED: '已发布', DISABLED: '已下架', IMPORTING: '导入中', READY: '就绪', ERROR: '导入失败', CREATING: '创建中', STARTING: '启动中', RESETTING: '重置中', STOPPING: '回收中', FINISHED: '已完成', FAILED: '启动失败', DESTROYED: '已销毁', running: '运行中', removed: '已移除', exited: '已退出', created: '已创建' }
const type = computed(() => ['READY', 'PUBLISHED', 'running'].includes(props.status) ? 'success' : ['ERROR', 'FAILED', 'exited'].includes(props.status) ? 'danger' : ['CREATING', 'STARTING', 'IMPORTING', 'RESETTING', 'STOPPING'].includes(props.status) ? 'warning' : 'info')
</script>
<template>
<el-tag :type="type" effect="light" round>{{ labels[status] || status }}</el-tag>
</template>
