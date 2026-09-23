"""Deliberately vulnerable, isolated teaching targets. Python standard library only.

Each image selects one scenario. Never publish these ports on a public host.
Supply-chain execution is modeled as data; SSRF is contained to a loopback service.
"""
import base64
import html
import json
import os
import secrets
import sqlite3
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from urllib.request import ProxyHandler, build_opener

SCENARIOS = {
    "access": ("A01 · 越权读取订单", "你以 alice 身份登录。订单 1001 属于你；订单编号连续。", '<a href="/orders?id=1001">查看我的订单</a>'),
    "config": ("A02 · 调试配置泄露", "运维曾将备份放在站点目录。先看看爬虫索引规则。", '<a href="/robots.txt">robots.txt</a>'),
    "supply": ("A03 · 不可信软件来源", "模拟主题安装器：同名组件可能来自不同源。本实验不执行上传代码。", '<a href="/registry">查看模拟组件仓库</a><form action="/install" method="post">来源 <input name="source" value="official">组件 <input name="package" value="lesson-theme"><button>安装主题</button></form>'),
    "crypto": ("A04 · 编码不是加密", "下载教学备份，分析所谓密文的存储格式。", '<a href="/backup">下载备份</a>'),
    "sqli": ("A05 · SQL 查询边界", "管理员登录使用了字符串拼接。请在表单中探索查询的引号边界。", '<form action="/login" method="post">用户 <input name="username" value="student">密码 <input name="password" type="password"><button>登录</button></form>'),
    "design": ("A06 · 优惠券重复核销", "账户余额 0，礼品售价 100。WELCOME 优惠券价值 50，规则规定每人只能使用一次。", '<a href="/balance">查看余额</a><form action="/redeem" method="post"><input name="coupon" value="WELCOME"><button>兑换优惠券</button></form><form action="/buy" method="post"><button>购买礼品</button></form>'),
    "auth": ("A07 · 找回流程绕过认证", "找回密码接口只接收用户名，却未验证身份。观察正常账户与 admin 的区别。", '<form action="/reset-password" method="post"><input name="username" value="student"><button>找回账户</button></form>'),
    "integrity": ("A08 · 未签名身份令牌", "身份令牌为 Base64 编码 JSON，服务器没有校验签名。", '<a href="/token">取得普通用户令牌</a><form action="/profile" method="post"><textarea name="token" aria-label="身份令牌"></textarea><button>读取身份资料</button></form>'),
    "logging": ("A09 · 登录失败未记录", "审计面板看起来平静，但登录失败既不记录也不告警。教学 PIN 只有 00、01、02、03 四个候选。", '<a href="/audit">查看审计记录</a><form action="/pin" method="post"><input name="pin" value="00"><button>验证 PIN</button></form>'),
    "exception": ("A10 · 异常时放行", "保险箱按照策略判断权限。当前策略版本为整数 1，该策略拒绝普通用户访问。", '<form action="/vault" method="post"><input name="policy_version" value="1"><button>打开保险箱</button></form>'),
    "xss": ("专项 · 反射型 XSS", "搜索结果未进行 HTML 编码。读取当前站点教学 Cookie 中的奖励，观察输入是否被当成脚本执行。", '<form action="/search"><input name="q" value="hello"><button>搜索</button></form>'),
    "ssrf": ("专项 · 服务端请求伪造", "预览器由服务器请求 URL。内部管理页只监听靶机的 127.0.0.1:9000，Kali 不能直接连接。", '<form action="/preview"><input name="url" value="http://127.0.0.1:9000/"><button>预览 URL</button></form>'),
}


class LabServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, scenario, flag):
        if scenario not in SCENARIOS:
            raise ValueError("Unknown LAB_SCENARIO")
        self.scenario, self.flag = scenario, flag
        self.lock = threading.Lock()
        self.wallets = {}
        self.internal_port = 9000
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        # Request bodies, Cookies and Flags must not enter container logs.
        pass

    def reply(self, text, status=200, content_type="text/html; charset=utf-8", cookie=None):
        data = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def page(self, body, status=200, cookie=None):
        title = SCENARIOS[self.server.scenario][0]
        self.reply('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CyberLab 教学靶机</title><style>body{font:16px/1.8 system-ui,sans-serif;max-width:860px;margin:48px auto;padding:0 24px;background:#f4f7f5;color:#203b34}main{background:white;border:1px solid #dce5df;padding:32px;border-radius:16px}input,textarea,button{font:inherit;padding:8px;margin:8px;max-width:90%}button{background:#286e5c;color:white;border:0;border-radius:6px}a{color:#287c69}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{color:#637c71}</style><main><small>CYBERLAB · 独立教学环境</small><h1>''' + title + '</h1>' + body + '<p><a href="/">返回实验首页</a></p></main></html>', status, cookie=cookie)

    def result(self, text, status=200):
        self.page('<pre>' + html.escape(text) + '</pre>', status)

    def do_GET(self):
        self.dispatch({})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 16384:
                return self.result("请求过大", 413)
            fields = parse_qs(self.rfile.read(length).decode(), keep_blank_values=True)
        except (ValueError, UnicodeError):
            return self.result("无效表单", 400)
        self.dispatch(fields)

    def dispatch(self, fields):
        lab, flag = self.server.scenario, self.server.flag
        parsed = urlsplit(self.path)
        path, query = parsed.path, parse_qs(parsed.query, keep_blank_values=True)
        value = lambda key, default="": fields.get(key, query.get(key, [default]))[0]
        if path == "/health":
            return self.reply("ok", content_type="text/plain")
        if path == "/":
            _, intro, form = SCENARIOS[lab]
            cookie = None
            if lab == "xss":
                cookie = "lab_reward=" + base64.b64encode(flag.encode()).decode() + "; Path=/; SameSite=Strict"
            return self.page('<p>' + intro + '</p>' + form, cookie=cookie)
        if lab == "access" and path == "/orders":
            # Missing ownership check; authentication alone is not authorization.
            orders = {"1001": {"owner": "alice", "item": "入门教材"}, "1002": {"owner": "bob", "delivery_note": flag}}
            return self.result(json.dumps(orders.get(value("id"), {"error": "订单不存在"}), ensure_ascii=False))
        if lab == "config" and path == "/robots.txt":
            return self.reply("User-agent: *\nDisallow: /backup/config.json\n", content_type="text/plain")
        if lab == "config" and path == "/backup/config.json":
            return self.result(json.dumps({"debug": True, "training_secret": flag}))
        if lab == "supply" and path == "/registry":
            return self.result(json.dumps({"official": {"lesson-theme": {"version": "1.0", "publisher": "course-team", "trusted": True}}, "community": {"lesson-theme": {"version": "9.9", "publisher": "unknown", "trusted": False, "note": "post-install 会读取教学凭据（数据模拟）"}}}, ensure_ascii=False))
        if lab == "supply" and path == "/install" and self.command == "POST":
            if value("package") != "lesson-theme" or value("source") not in ("official", "community"):
                return self.result("组件不存在", 404)
            # Model a package lifecycle hook without executing arbitrary code.
            return self.result("已安装官方主题" if value("source") == "official" else "未验证发布者的组件执行了模拟安装钩子，读取到教学凭据：" + flag)
        if lab == "crypto" and path == "/backup":
            return self.reply(json.dumps({"format": "base64", "encrypted_secret": base64.b64encode(flag.encode()).decode()}), content_type="application/json")
        if lab == "sqli" and path == "/login" and self.command == "POST":
            with sqlite3.connect(":memory:") as db:
                db.execute("CREATE TABLE users (username TEXT, password TEXT)")
                db.execute("INSERT INTO users VALUES (?, ?)", ("admin", secrets.token_hex(24)))
                sql = "SELECT username FROM users WHERE username = '" + value("username") + "' AND password = '" + value("password") + "'"
                try:
                    row = db.execute(sql).fetchone()
                except sqlite3.Error:
                    return self.result("SQL 语法错误；检查字符串引号边界。", 400)
            return self.result(flag if row else "登录失败", 200 if row else 403)
        if lab == "design" and path in ("/balance", "/redeem", "/buy"):
            cookies = SimpleCookie()
            try:
                cookies.load(self.headers.get("Cookie", ""))
            except Exception:
                pass
            sid = cookies["wallet"].value if "wallet" in cookies else secrets.token_hex(16)
            with self.server.lock:
                balance = self.server.wallets.get(sid, 0)
                if path == "/redeem" and self.command == "POST" and value("coupon") == "WELCOME":
                    balance += 50  # Missing one-time redemption ledger.
                if path == "/buy" and self.command == "POST" and balance >= 100:
                    self.server.wallets[sid] = balance - 100
                    return self.result(flag)
                if len(self.server.wallets) > 2000:
                    self.server.wallets.clear()
                self.server.wallets[sid] = balance
            return self.page(f'<p>余额：{balance}；礼品需要 100。</p>', cookie=f"wallet={sid}; Path=/; HttpOnly; SameSite=Strict")
        if lab == "auth" and path == "/reset-password" and self.command == "POST":
            return self.result(flag if value("username") == "admin" else "普通用户恢复完成。管理员用户名为 admin。")
        if lab == "integrity" and path == "/token":
            return self.reply(base64.b64encode(b'{"user":"student","role":"student"}').decode(), content_type="text/plain")
        if lab == "integrity" and path == "/profile" and self.command == "POST":
            try:
                identity = json.loads(base64.b64decode(value("token"), validate=True))
                admin = isinstance(identity, dict) and identity.get("role") == "admin"
            except (ValueError, UnicodeError):
                return self.result("令牌格式错误", 400)
            return self.result(flag if admin else "普通用户资料")
        if lab == "logging" and path == "/audit":
            return self.reply(json.dumps({"failed_logins": [], "alerts": [], "policy": "失败应记录，连续三次失败应告警"}, ensure_ascii=False), content_type="application/json")
        if lab == "logging" and path == "/pin" and self.command == "POST":
            return self.result(flag if value("pin") == "03" else "验证失败", 200 if value("pin") == "03" else 403)
        if lab == "exception" and path == "/vault" and self.command == "POST":
            try:
                allowed = {1: False, 2: False}[int(value("policy_version"))]
            except (ValueError, KeyError):
                allowed = True  # Vulnerability: fail-open on malformed input.
            return self.result(flag if allowed else "策略拒绝访问", 200 if allowed else 403)
        if lab == "xss" and path == "/search":
            return self.page('<p>搜索结果：' + value("q") + '</p>')  # Deliberately unescaped.
        if lab == "ssrf" and path == "/preview":
            try:
                target = urlsplit(value("url"))
                # Lab containment boundary, not a complete production SSRF defense.
                if target.scheme != "http" or target.hostname not in ("127.0.0.1", "localhost") or target.port != self.server.internal_port:
                    return self.result("教学预览器仅演示靶机内部的回环管理服务。", 400)
                with build_opener(ProxyHandler({})).open(value("url"), timeout=3) as response:
                    content = response.read(16384).decode()
                return self.result(content)
            except Exception:
                return self.result("预览失败", 502)
        return self.result("未找到页面", 404)


class InternalHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        data = (self.server.flag if self.path == "/admin" else "Internal service: /admin").encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    scenario = os.environ["LAB_SCENARIO"]
    flag = os.environ.get("LAB_FLAG", "flag{local_training_only}")
    server = LabServer(("0.0.0.0", 8000), scenario, flag)
    if scenario == "ssrf":
        internal = ThreadingHTTPServer(("127.0.0.1", 9000), InternalHandler)
        internal.flag = flag
        threading.Thread(target=internal.serve_forever, daemon=True).start()
    server.serve_forever()
