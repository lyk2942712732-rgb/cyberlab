<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import RFB from '@novnc/novnc'
import { post } from '../../api/http'
const route = useRoute(), screen = ref<HTMLDivElement>(), status = ref('正在连接桌面…'), connected = ref(false), connecting = ref(false)
let rfb: RFB | undefined, ws: WebSocket | undefined, disposed = false, handshakeTimer: ReturnType<typeof setTimeout> | undefined
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
          rfb.scaleViewport = true; rfb.resizeSession = true
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
<div ref="screen" class="novnc-screen"/>
<div v-if="!connected" class="novnc-overlay">
<div class="desktop-glyph">&gt;_</div>
<p>{{ status }}</p>
<el-button :loading="connecting" @click="connect">重新连接</el-button>
</div>
<div v-if="connected" class="novnc-toolbar">
<span>CyberLab / Kali</span>
<el-button size="small" @click="rfb?.sendCtrlAltDel()">Ctrl + Alt + Del</el-button>
</div>
</div>
</template>
