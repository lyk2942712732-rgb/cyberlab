declare module '@novnc/novnc' {
  export default class RFB extends EventTarget {
    constructor(target: HTMLElement, urlOrChannel: string | WebSocket, options?: object)
    scaleViewport: boolean
    resizeSession: boolean
    viewOnly: boolean
    disconnect(): void
    sendCtrlAltDel(): void
  }
}
