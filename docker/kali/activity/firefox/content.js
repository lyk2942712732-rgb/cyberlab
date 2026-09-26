(() => {
  const values = new WeakMap();
  const editable = el => el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement || el?.isContentEditable;
  function describe(el) {
    return {tag: el.tagName?.toLowerCase(), id: el.id || null, name: el.getAttribute?.('name'),
      label: (el.getAttribute?.('aria-label') || el.labels?.[0]?.textContent || el.innerText || el.getAttribute?.('title') || '').trim().slice(0, 256)};
  }
  function value(el) {
    if (el.type === 'password' || /(?:password|current-password|new-password|one-time-code)/i.test(el.autocomplete || '')) return '[隐藏]';
    if (el.type === 'file') return '[文件选择]';
    if (['checkbox', 'radio'].includes(el.type)) return el.checked;
    if (el instanceof HTMLSelectElement && el.multiple) return [...el.selectedOptions].map(option => option.value);
    const result = el.isContentEditable ? el.textContent : el.value;
    return result?.length > 8192 ? '[内容超出记录上限]' : result;
  }
  function send(type, data) {
    browser.runtime.sendMessage({type, data: {page: location.href, ...data}}).catch(() => {});
  }
  function completed(el, completion) {
    if (!editable(el)) return;
    const final = value(el), previous = values.get(el);
    if (JSON.stringify(previous) === JSON.stringify(final)) return;
    values.set(el, final);
    send('web.change', {field: describe(el), value: final, completion});
  }
  document.addEventListener('focusin', event => {
    if (event.isTrusted && editable(event.target)) values.set(event.target, value(event.target));
  }, true);
  document.addEventListener('change', event => {
    if (event.isTrusted) completed(event.target, 'change');
  }, true);
  document.addEventListener('focusout', event => {
    if (event.isTrusted) completed(event.target, 'focus_left');
  }, true);
  document.addEventListener('keydown', event => {
    if (event.isTrusted && event.key === 'Enter' && !event.isComposing && event.target instanceof HTMLInputElement) completed(event.target, 'enter');
  }, true);
  document.addEventListener('click', event => {
    if (!event.isTrusted) return;
    const el = event.composedPath().find(item => item?.matches?.('button,a,input,[role="button"],select,label')) || event.target;
    send('web.click', {target: describe(el), button: event.button, x: event.screenX, y: event.screenY});
  }, true);
  document.addEventListener('submit', event => {
    if (!event.isTrusted) return;
    const fields = [...event.target.elements].filter(el => editable(el) && !el.disabled && !['hidden', 'submit', 'button', 'reset'].includes(el.type));
    if (fields.length > 100) {
      send('web.submit', {form: describe(event.target), error: '表单字段数超出上限'});
      return;
    }
    const result = fields.map(el => ({...describe(el), value: value(el)}));
    for (const el of fields) values.set(el, value(el));
    send('web.submit', {form: describe(event.target), fields: result, semantics: 'submit_attempt_not_server_success'});
  }, true);
})();
