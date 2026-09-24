<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import RFB from '@novnc/novnc'
import { post } from '../../api/http'
const route = useRoute(), screen = ref<HTMLDivElement>(), status = ref('正在连接桌面…'), connected = ref(false), connecting = ref(false)
const clipboardOpen = ref(false), clipboardDraft = ref(''), remoteClipboard = ref(''), clipboardHint = ref('支持双向文本复制'), clipboardBusy = ref(false)
let rfb: RFB | undefined, ws: WebSocket | undefined, disposed = false, handshakeTimer: ReturnType<typeof setTimeout> | undefined
let suppressPasteKeyUp = false
let manualClipboardReady = false
function sendClipboard(manual = true) {
  if (!connected.value || !rfb) return
  rfb.clipboardPasteFrom(clipboardDraft.value)
  manualClipboardReady = manual
  clipboardHint.value = '已发送到 Kali，可在目标应用粘贴；终端使用 Ctrl+Shift+V。'
}
async function readClipboard(paste = false, terminal = false) {
  if (clipboardBusy.value || !connected.value) return
  clipboardBusy.value = true
  const client = rfb
  try {
    const text = paste && manualClipboardReady ? clipboardDraft.value : await navigator.clipboard.readText()
    if (disposed || client !== rfb || !connected.value) return
    clipboardDraft.value = text
    sendClipboard(false)
    if (paste && client) {
      // The permission prompt may outlive the physical modifier keys. Send a
      // complete chord rather than relying on their state across the await.
      for (const [key, code] of [[0xffe3, 'ControlLeft'], [0xffe4, 'ControlRight'], [0xffe1, 'ShiftLeft'], [0xffe2, 'ShiftRight'], [0xffeb, 'MetaLeft'], [0xffec, 'MetaRight']] as const) client.sendKey(key, code, false)
      client.sendKey(0xffe3, 'ControlLeft', true)
      if (terminal) client.sendKey(0xffe1, 'ShiftLeft', true)
      // X11 needs the uppercase keysym for the terminal's Ctrl+Shift+V shortcut.
      client.sendKey(terminal ? 0x56 : 0x76, 'KeyV')
      if (terminal) client.sendKey(0xffe1, 'ShiftLeft', false)
      client.sendKey(0xffe3, 'ControlLeft', false)
      client.focus()
    }
  } catch {
    clipboardHint.value = '浏览器未允许读取剪贴板，请在下方粘贴文本，再点击“发送到 Kali”。'
    clipboardOpen.value = true
  } finally { clipboardBusy.value = false }
}
function pasteShortcut(event: KeyboardEvent) {
  if (event.code !== 'KeyV' || !(event.ctrlKey || event.metaKey) || event.altKey) return
  event.preventDefault(); event.stopImmediatePropagation()
  suppressPasteKeyUp = true
  if (!event.repeat) void readClipboard(true, event.shiftKey)
}
function pasteKeyUp(event: KeyboardEvent) {
  if (event.code === 'KeyV' && suppressPasteKeyUp) {
    event.preventDefault(); event.stopImmediatePropagation(); suppressPasteKeyUp = false
  }
}
async function copyRemoteClipboard() {
  try {
    await navigator.clipboard.writeText(remoteClipboard.value)
    clipboardHint.value = '已复制到本机剪贴板。'
  } catch { clipboardHint.value = '浏览器未允许写入剪贴板，请选中下方 Kali 文本，按 Ctrl+C 复制。' }
}
function receiveClipboard(event: Event) {
  remoteClipboard.value = (event as CustomEvent<{ text: string }>).detail.text
  void copyRemoteClipboard()
}
async function connect() {
  if (connecting.value) return
  connecting.value = true; connected.value = false; status.value = '正在连接桌面…'
  rfb?.disconnect(); ws?.close(); clearTimeout(handshakeTimer)
  try {
    const { ticket } = await post<{ ticket: string }>(`/lab-sessions/${route.params.id}/desktop-ticket`)
    if (disposed) return
    const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/lab-sessions/${route.params.id}/desktop`)
    socket.binaryType = 'arraybuffer'
    ws = socket
    handshakeTimer = setTimeout(() => { socket.close(); connecting.value = false; status.value = '连接超时，请重试。' }, 20000)
    socket.onopen = () => socket.send(JSON.stringify({ ticket }))
    socket.onerror = () => { connecting.value = false; status.value = '桌面连接失败，请确认实验处于就绪状态。' }
    socket.onclose = () => { clearTimeout(handshakeTimer); connected.value = false; connecting.value = false; status.value = '桌面连接已断开。实验到期或重置后连接会自动关闭。' }
    socket.onmessage = event => {
      if (typeof event.data !== 'string') return
      try {
        if (JSON.parse(event.data).ready && screen.value) {
          socket.onmessage = null
          clearTimeout(handshakeTimer)
          rfb = new RFB(screen.value, socket)
          // Keep Kali's 1440x900 framebuffer stable for OpenAdapt recording.
          // Browser resizing and fullscreen only scale the local canvas.
          rfb.scaleViewport = true
          rfb.resizeSession = false
          rfb.addEventListener('clipboard', receiveClipboard)
          rfb.addEventListener('connect', () => { connected.value = true; connecting.value = false })
          rfb.addEventListener('disconnect', () => { connected.value = false; connecting.value = false; status.value = '桌面连接已断开，可尝试重新连接。' })
          rfb.addEventListener('securityfailure', () => { status.value = '桌面握手失败，请联系教学管理员。'; connecting.value = false })
        }
      } catch { socket.close() }
    }
  } catch { status.value = '无法获取桌面访问凭证，请返回实验页面重试。'; connecting.value = false }
}
onMounted(connect)
onBeforeUnmount(() => { disposed = true; clearTimeout(handshakeTimer); rfb?.disconnect(); ws?.close() })
</script>
<template>
<div class="novnc-view">
<div ref="screen" class="novnc-screen" @keydown.capture="pasteShortcut" @keyup.capture="pasteKeyUp"/>
<div v-if="!connected" class="novnc-overlay">
<div class="desktop-glyph">&gt;_</div>
<p>{{ status }}</p>
<el-button :loading="connecting" @click="connect">重新连接</el-button>
</div>
<div v-if="connected" class="novnc-toolbar">
<span>CyberLab / Kali</span>
<div class="novnc-toolbar-actions">
<span class="clipboard-hint" role="status" :title="clipboardHint">{{ clipboardHint }}</span>
<el-button size="small" @click="clipboardOpen = true">剪贴板</el-button>
<el-button size="small" @click="rfb?.sendCtrlAltDel()">Ctrl + Alt + Del</el-button>
</div>
</div>
<el-dialog v-model="clipboardOpen" title="文本剪贴板" width="520px" class="clipboard-dialog" :close-on-click-modal="false" @closed="rfb?.focus()">
<p class="clipboard-help">本机 → Kali：在桌面按 Ctrl+V，终端按 Ctrl+Shift+V。也可在这里手动传递文本。</p>
<label for="clipboard-to-kali">发送到 Kali</label>
<el-input id="clipboard-to-kali" v-model="clipboardDraft" type="textarea" :rows="3" placeholder="在此粘贴本机文本"/>
<div class="clipboard-buttons">
<el-button :disabled="!connected" :loading="clipboardBusy" @click="readClipboard()">读取本机剪贴板</el-button>
<el-button type="primary" :disabled="!connected" @click="sendClipboard()">发送到 Kali</el-button>
</div>
<label for="clipboard-from-kali">从 Kali 复制的文本</label>
<el-input id="clipboard-from-kali" :model-value="remoteClipboard" type="textarea" :rows="3" readonly placeholder="在 Kali 应用中复制文本后，会显示在这里"/>
<div class="clipboard-buttons"><el-button @click="copyRemoteClipboard">复制到本机</el-button></div>
<p class="clipboard-help" role="status">{{ clipboardHint }}</p>
</el-dialog>
</div>
</template>
