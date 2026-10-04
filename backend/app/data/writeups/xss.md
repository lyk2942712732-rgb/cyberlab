# 反射型 XSS 与输出编码 · 参考解答

## 目标与实现边界

`/search` 把 q 直接拼入 HTML，浏览器可能将其作为标记或脚本执行。首次访问靶机首页会设置非 HttpOnly 的教学 Cookie `lab_reward`，值是 Base64 编码的 Flag。本场景只读取该专属靶机的教学 Cookie，不向外部服务发送任何数据。

## 复现步骤

1. **先在同一个 Kali Firefox 会话中访问首页**，确保浏览器拿到教学 Cookie。
2. 在搜索表单填 `hello` 并提交，观察普通文字结果。
3. 再填 `<b>probe</b>`。若 probe 以粗体呈现而不是显示尖括号，说明输入被当成 HTML 解析；这仍不等同于已经证明 JavaScript 执行。
4. 在同一搜索输入中提交以下内容，把解码后的教学值追加到当前页面文本中：

```html
<script>document.body.insertAdjacentText('beforeend', atob(document.cookie.split('lab_reward=')[1].split(';')[0]))</script>
```

5. 预期当前页面出现解码后的 Flag。记录脚本执行现象，复制页面中的完整值并提交到平台。

如需仅检查服务器反射行为，可以在 Kali 执行：

```bash
TARGET='http://TARGET_IP:8000'
curl -sS --get "$TARGET/search" --data-urlencode 'q=<b>probe</b>'
```

**curl 不会执行 JavaScript，也不会自动继承浏览器 Cookie**。返回 HTML 中包含 payload 只证明反射，完整脚本效果应在浏览器中核实。

## 常见失败与解释

- 未先打开首页、换了浏览器配置/站点 IP 或 Cookie 被清除时，lab_reward 可能不存在。回到同一靶机首页后再试。
- 输入需要英文半角引号和完整的 script 标签；直接把未编码的 payload 拼进地址栏可能损坏参数，应使用搜索表单。
- Base64 解码只是将已被脚本读取的教学值恢复为明文；根因是未经上下文编码的 HTML 输出，不是 Base64 本身导致脚本执行。

## 修复思路与回归

将 q 作为 HTML 文本上下文输出时正确编码（本 Python 页面可使用 `html.escape`）；避免不可信 innerHTML。需要允许部分 HTML 时使用成熟净化库。敏感 Cookie 设置 HttpOnly，CSP 作为纵深防御；仅添加 HttpOnly 不能阻止脚本操作页面或发起同源请求。

回归：普通搜索正常显示；`<b>probe</b>` 作为文字展示；script 或其他可执行标记不会执行；合法文字中的特殊字符显示正确。不要只测试这一条 payload 就认为覆盖所有输出上下文。

## 本实验评估要点

分别评价普通输入、HTML 解析与脚本执行的证据。接受在当前靶机页面显示教学 Cookie 解码值的等价脚本；不要求使用弹窗。采集的搜索提交或含脚本的 URL 不证明浏览器已经执行，需页面结果、受控截图或判题证据支持结论。
