<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
const props = defineProps<{ content?: string }>()
const html = computed(() => DOMPurify.sanitize(marked.parse(props.content || '', { async: false }) as string, { FORBID_TAGS: ['style', 'iframe'], FORBID_ATTR: ['style'] }))
</script>
<template>
<div class="markdown" v-html="html" />
</template>
