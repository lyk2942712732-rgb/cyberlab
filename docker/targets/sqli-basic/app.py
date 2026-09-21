"""Intentionally vulnerable, isolated classroom demo. Never expose publicly."""
import html
import os
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

database = "/tmp/demo.db"
with sqlite3.connect(database) as db:
    db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT)")
    db.execute("DELETE FROM users")
    db.execute("INSERT INTO users VALUES (?, ?)", ("admin", secrets.token_hex(24)))
flag = os.environ.get("LAB_FLAG", "flag{configure_lab_flag}")

PAGE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>CyberLab SQL 注入演示靶机</title>
<style>body{background:#10231e;color:#dceacb;font:16px/1.8 sans-serif;max-width:680px;margin:70px auto;padding:24px}h1{font-size:28px}input,button{padding:12px;margin:8px 0;width:100%;box-sizing:border-box}small{color:#98b284}code{background:#243e30;padding:4px}</style>
<h1>教学档案查询系统</h1><p>本页面仅用于 CyberLab 授权实验环境。</p>
<form action="/login" method="get"><label>用户名<input name="username" placeholder="admin" maxlength="200"></label><label>密码<input name="password" type="password" maxlength="200"></label><button>登录</button></form>
<p>{message}</p><small>学习目标：理解未参数化查询的风险，并思考如何修复。</small></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        message = "请登录以访问教学档案。"
        if parsed.path == "/login":
            values = parse_qs(parsed.query)
            username = values.get("username", [""])[0][:200]
            password = values.get("password", [""])[0][:200]
            # Intentional vulnerability confined to this local, non-production target.
            query = f"SELECT username FROM users WHERE username = '{username}' AND password = '{password}'"
            try:
                with sqlite3.connect(database) as db:
                    row = db.execute(query).fetchone()
                message = f"登录成功，实验 Flag：<code>{html.escape(flag)}</code>" if row else "用户名或密码错误。"
            except sqlite3.Error:
                message = "SQL 查询错误，请检查输入。"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.replace("{message}", message).encode())


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
