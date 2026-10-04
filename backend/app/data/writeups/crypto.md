# 密码学失效：误把编码当加密 · 参考解答

## 目标与实现边界

`/backup` 返回 JSON，其中 `format=base64`，`encrypted_secret` 只是编码后的 Flag。字段名字包含 encrypted 不会使数据获得机密性；此转换没有密钥，任何拿到备份的人都可以反向解码。

## 复现步骤

1. 打开 `/backup`，记录 format 与 encrypted_secret。首页不直接给出明文奖励。
2. 在 Kali 下载 JSON 并用标准库解码，注意解码的是字段值，不是整个 JSON 文件：

```bash
TARGET='http://TARGET_IP:8000'
curl -sS "$TARGET/backup" -o /tmp/cyberlab-backup.json
python3 - <<'PY'
import base64, json
with open('/tmp/cyberlab-backup.json', encoding='utf-8') as f:
    backup = json.load(f)
print('存储格式:', backup['format'])
print(base64.b64decode(backup['encrypted_secret'], validate=True).decode())
PY
```

3. 输出应为可读的本次 Flag。记录“无须密钥即可恢复”的现象，再提交 Flag。

## 预期现象与常见误区

- Base64 的字母表、`=` 填充可作为识别线索，但字符串像 Base64 不足以证明它的含义；这里还需要 JSON 的格式说明与成功解码结果。
- 如果出现 padding/解码错误，检查是否漏掉末尾 `=`、复制了引号，或误将完整 JSON 当成编码串。
- 这不是破解加密，也不是撞库或口令暴力破解。HTTPS 可以保护传输，但不能使已下载的 Base64 备份自动获得机密性。

## 修复思路与回归

先减少不必要的敏感数据存储并限制备份访问。需要还原的秘密应使用成熟的认证加密方案和独立受控的密钥；用于登录校验的口令应使用专用口令哈希库，不能用 Base64 或普通可逆加密代替。

回归检查：未授权访问不能取得备份；仅得到存储文件且没有受控密钥时，不能直接恢复秘密；篡改加密内容会被拒绝；正常授权恢复仍能进行。不要把“Base64 解码报错”当作加密方案安全的充分证明。

## 本实验评估要点

核实原始字段、实际解码操作及输出；能区分编码、加密、哈希的用途。若采集只保存了 Python 命令而没有输出，可确认解码尝试，但结果需补充终端输出、截图或判题证据。
