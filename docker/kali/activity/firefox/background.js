const queue = [];
let port, pending, lost = false;
function badge(error) {
  browser.browserAction.setBadgeText({text: error ? '!' : ''});
  browser.browserAction.setBadgeBackgroundColor({color: '#dc2626'});
  browser.browserAction.setTitle({title: error ? '操作采集异常：部分操作可能未保存' : 'CyberLab 操作采集正常'});
}
function connect() {
  if (port) return;
  port = browser.runtime.connectNative('cyberlab_activity');
  port.onMessage.addListener(reply => {
    if (!reply.ok) lost = true;
    badge(lost);
    pending = null;
    pump();
  });
  port.onDisconnect.addListener(() => {
    port = null;
    if (pending && queue.length < 128) queue.unshift(pending);
    pending = null;
    lost = true;
    badge(true);
  });
}
function enqueue(message) {
  if (queue.length >= 128) { lost = true; badge(true); return; }
  queue.push(message);
  pump();
}
function pump() {
  if (pending || !queue.length) return;
  try {
    connect();
    pending = queue.shift();
    port.postMessage(pending);
  } catch (_) {
    if (pending && queue.length < 128) queue.unshift(pending);
    lost = true; pending = null; badge(true);
  }
}
browser.runtime.onMessage.addListener((message, sender) => {
  if (sender.id !== browser.runtime.id || !sender.tab || !['web.change', 'web.click', 'web.submit'].includes(message.type)) return;
  enqueue({id: crypto.randomUUID(), type: message.type, data: {...message.data, tab: sender.tab.id, frame: sender.frameId}});
});
browser.webNavigation.onCommitted.addListener(event => {
  if (!/^https?:/.test(event.url) || event.frameId !== 0) return;
  enqueue({id: crypto.randomUUID(), type: 'web.navigate', data: {url: event.url, transition: event.transitionType, qualifiers: event.transitionQualifiers, tab: event.tabId, semantics: 'navigation_not_address_bar_text'}});
});
setInterval(() => enqueue({control: 'provider', status: lost ? 'partial' : 'ready'}), 5000);
enqueue({control: 'provider', status: 'ready'});
