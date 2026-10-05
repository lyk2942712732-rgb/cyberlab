<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'

const props = defineProps<{ steps: { title: string; text: string; evidence_ids: string[] }[] }>()
const emit = defineEmits<{ evidence: [ids: string[]] }>()
const board = ref<HTMLOListElement>(), links = ref<string[]>([]), opened = ref<number | null>(null)
const markerId = useId().replace(/:/g, '') + '-arrow'
let observer: ResizeObserver | undefined, frame = 0
const column = (index: number) => Math.floor(index / 2) % 2 === 0 ? index % 2 + 1 : 2 - index % 2
function draw() {
  if (!board.value) return
  const origin = board.value.getBoundingClientRect()
  const boxes = [...board.value.querySelectorAll<HTMLElement>('.path-stop')].map(node => node.getBoundingClientRect())
  links.value = boxes.slice(0, -1).map((a, index) => {
    const b = boxes[index + 1]!, y1 = a.top - origin.top + a.height / 2, y2 = b.top - origin.top + b.height / 2
    if (index % 2 === 0) {
      const forward = column(index) === 1
      return `M ${ (forward ? a.right : a.left) - origin.left } ${y1} L ${ (forward ? b.left : b.right) - origin.left } ${y2}`
    }
    const right = column(index) === 2, x = (right ? a.right : a.left) - origin.left
    const bend = x + (right ? 26 : -26)
    return `M ${x} ${y1} C ${bend} ${y1}, ${bend} ${y2}, ${x} ${y2}`
  })
}
function schedule() { cancelAnimationFrame(frame); frame = requestAnimationFrame(draw) }
onMounted(() => { observer = new ResizeObserver(schedule); if (board.value) observer.observe(board.value); schedule() })
watch(() => props.steps, async () => { opened.value = null; await nextTick(); observer?.disconnect(); if (board.value) observer?.observe(board.value); schedule() })
onBeforeUnmount(() => { observer?.disconnect(); cancelAnimationFrame(frame) })
function dismiss(event: KeyboardEvent) { opened.value = null; (event.target as HTMLElement).blur() }
</script>

<template>
  <div class="path-wrap">
    <p v-if="!steps.length" class="small muted">本次没有可展示的关键操作。</p>
    <ol v-else ref="board" class="path-board" aria-label="按时间排列的操作路径">
      <svg class="path-links" aria-hidden="true">
        <defs><marker :id="markerId" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M 1 1 L 5 3.5 L 1 6" fill="none" stroke="currentColor" stroke-width="1.2" /></marker></defs>
        <path v-for="(line, index) in links" :key="index" :d="line" :marker-end="`url(#${markerId})`" />
      </svg>
      <li v-for="(step, index) in steps" :key="index" class="path-stop" :class="{ 'detail-open': opened === index, 'right-column': column(index) === 2 }"
        :style="{ gridColumn: column(index), gridRow: Math.floor(index / 2) + 1 }" @keydown.esc="dismiss">
        <button class="step-title" :aria-describedby="`${markerId}-detail-${index}`"
          @click="opened = opened === index ? null : index">
          <span class="step-number">{{ String(index + 1).padStart(2, '0') }}</span><strong>{{ step.title }}</strong>
        </button>
        <button v-if="step.evidence_ids.length" class="step-evidence" :aria-label="`${step.title}：查看依据`" @click="emit('evidence', step.evidence_ids)">查看依据 <span aria-hidden="true">↗</span></button>
        <span v-else class="small muted step-empty">无可展开依据</span>
        <div :id="`${markerId}-detail-${index}`" class="step-detail" role="tooltip">{{ step.text }}</div>
      </li>
    </ol>
    <p v-if="steps.length" class="path-hint small muted">按序号阅读 · 悬浮或点按节点查看操作说明</p>
  </div>
</template>

<style scoped>
.path-wrap { min-width: 0; }
.path-board { position: relative; list-style: none; padding: 4px 24px; margin: 8px 0 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 30px 34px; }
.path-links { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; color: var(--accent); }
.path-links > path { fill: none; stroke: var(--accent-line); stroke-width: 1.5; }
.path-stop { position: relative; z-index: 1; display: flex; flex-direction: column; min-width: 0; min-height: 94px; background: var(--surface-2); border: 1px solid var(--rule); border-radius: 9px; }
.path-stop:hover, .path-stop:focus-within, .path-stop.detail-open { z-index: 3; border-color: var(--accent-line); }
.step-title { display: flex; align-items: baseline; gap: 9px; width: 100%; padding: 15px 13px 8px; text-align: left; color: var(--ink); background: transparent; border: 0; cursor: pointer; font: inherit; }
.step-title strong { font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.step-number { color: var(--accent); font: 11px var(--mono); flex-shrink: 0; }
.step-evidence { display: flex; justify-content: space-between; align-items: center; margin: auto 13px 12px; padding: 0; color: var(--accent); background: transparent; border: 0; font: inherit; font-size: 12px; cursor: pointer; }
.step-empty { padding: 0 13px 12px; }
.step-detail { display: none; position: absolute; left: 0; bottom: calc(100% + 10px); width: 290px; max-width: calc(100vw - 64px); box-sizing: border-box; padding: 13px 15px; background: var(--surface-3); border: 1px solid var(--accent-line); border-radius: 8px; box-shadow: 0 10px 25px #0006; color: var(--ink-2); font-size: 13px; line-height: 1.8; overflow-wrap: anywhere; pointer-events: none; }
.right-column .step-detail { left: auto; right: 0; }
.path-stop:hover .step-detail, .path-stop:focus-within .step-detail, .path-stop.detail-open .step-detail { display: block; }
.path-hint { margin: 12px 24px 0; font-size: 11px; }
@media (max-width: 480px) { .path-board { padding-inline: 20px; column-gap: 20px; } .step-title { gap: 5px; padding: 12px 8px 8px; } .step-title strong { font-size: 12px; } .step-evidence { margin-inline: 8px; } }
</style>
