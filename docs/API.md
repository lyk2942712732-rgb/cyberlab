# API 约定

所有业务接口以 `/api` 开头，使用 JSON。登录后发送 `Authorization: Bearer <access_token>`。只有教学管理端使用 `/api/admin/*`；普通注册不接受 role 字段。

成功：`{"data": ...}`。失败：`{"error":{"message":"可读说明","code":"可选稳定错误码"}}`。输入校验失败额外返回 `fields`，不回显密码或 Flag 输入。常用状态码：401 未登录，403 角色不足，404 记录不存在/不属于本人，409 状态冲突，413 文件过大，415 文件类型错误，422 参数错误，429 限流/并发容量已满，503 基础服务不可用。

本次未运行接口；示例用于描述代码约定。

## 认证与学习

| 方法 | 路径 | 内容 |
| --- | --- | --- |
| POST | `/auth/register` | username、password、real_name、student_number；固定 STUDENT |
| POST | `/auth/login` | username、password；返回 access_token 与安全用户信息 |
| GET | `/auth/me` | 当前用户，不含 password_hash |
| GET | `/courses` | 学生仅看到已发布课程与课时 |
| GET | `/courses/{id}` | Course → Chapters → Lessons |
| GET | `/lessons/{id}` | Markdown 内容与 related_lab_id |
| POST | `/lessons/{id}/complete` | 幂等记录学习完成 |
| GET | `/me/progress` | 当前用户课时完成记录 |
| GET | `/labs` | 可见实验列表，永不含正确 Flag |
| GET | `/labs/{id}` | 实验说明、目标、步骤、资源和 target_port |
| GET | `/me/sessions` | 本人的实验历史 |
| GET | `/me/scores` | 按用户/实验聚合的完成情况、成绩和提交次数 |

## 实验生命周期

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| POST | `/labs/{id}/sessions` | STUDENT 创建实验，202；同一活动实验重复启动返回原 Session |
| GET | `/lab-sessions/{id}` | 学生仅本人、管理员可访问；含 target_ip、lab.target_port、实例状态与过期时间 |
| POST | `/lab-sessions/{id}/reset` | 202；只允许未到期 READY 实验；不延长 TTL |
| POST | `/lab-sessions/{id}/stop` | 202；持久化 STOPPING 命令，销毁完成后 DESTROYED |
| POST | `/lab-sessions/{id}/submit` | `{ "flag": "flag{...}" }`；每次均记录 |
| POST | `/lab-sessions/{id}/desktop-ticket` | 签发两分钟有效的一次性桌面票据 |
| WS | `/lab-sessions/{id}/desktop` | 首帧传票据，再进入二进制 VNC 协议 |

启动响应示例：

```json
{
  "data": {
    "id": "<session_uuid>",
    "status": "CREATING",
    "target_ip": null,
    "expires_at": "2026-09-21T12:00:00Z",
    "instances": [],
    "lab": { "name": "SQL 注入基础实验", "target_port": 8000 }
  }
}
```

响应同时包含其他公开 Session/Template 字段。轮询到 READY 后申请桌面票据：

```json
{
  "data": {
    "ticket": "<short_lived_jwt>",
    "desktop_url": "/desktop/<session_uuid>",
    "expires_in": 120
  }
}
```

建立同源 WebSocket，首帧发送 `{"ticket":"<short_lived_jwt>"}`；收到 `{"ready":true}` 后交给 noVNC。票据不写入 URL，不能代替普通 API access token。票据在握手时检查过期，已经建立的连接受 Session TTL/状态/代次实时约束。

Flag 响应为 `{"data":{"correct":true,"score":100,"submission_id":"..."}}` 或 `correct=false, score=0`，不会返回正确答案或回显提交字符串。

## 教学管理

| 方法 | 路径 | 内容 |
| --- | --- | --- |
| GET | `/admin/dashboard` | 学生、课程、实验、运行和当日完成统计 |
| POST / PUT / DELETE | `/admin/courses[/{id}]` | 课程增改删 |
| POST / PUT / DELETE | `/admin/chapters[/{id}]` | 章节增改删 |
| POST / PUT / DELETE | `/admin/lessons[/{id}]` | 课时增改删、Markdown、发布状态、关联实验 |
| POST / PUT / DELETE | `/admin/labs[/{id}]` | 实验模板增改删；有历史记录时删除转为下架 |
| GET | `/admin/labs/{id}` | 唯一包含正确 Flag 的模板查询接口 |
| POST | `/admin/images/upload` | multipart：`display_name` 和 `file`，返回 202 |
| GET | `/admin/images` | 镜像元数据、导入状态及错误说明 |
| DELETE | `/admin/images/{id}` | 经编排器安全删除 Docker Image，再删除数据库行 |
| GET | `/admin/students` | 学生完成数、平均成绩与最近完成时间 |
| GET | `/admin/students/{id}` | 学习进度与各实验成绩 |
| GET | `/admin/scores` | 全部学生实验成绩 |
| GET | `/admin/lab-sessions` | 包含学生信息的实验实例列表 |
| POST | `/admin/lab-sessions/{id}/stop` | 强制停止实验 |

列表复用 `/courses`、`/labs`，管理员可查看草稿/下架记录；这些公共路径即使由管理员调用也不返回 Flag。

实验模板创建/完整更新示例：

```json
{
  "name": "SQL 注入基础实验",
  "description": "理解查询边界与输入处理",
  "objective": "掌握参数化查询的意义",
  "steps": "在 Kali 内访问实验页显示的靶机地址。",
  "category": "Web 安全",
  "difficulty": "BEGINNER",
  "target_image_id": "<target_images_uuid>",
  "target_port": 8000,
  "duration_minutes": 120,
  "cpu_limit": 1,
  "memory_limit": 512,
  "flag": "flag{sqli_success}",
  "status": "PUBLISHED"
}
```

`target_port` 必填 1–65535；时长 5–480 分钟；CPU 0.25–4 核；靶机内存 64–4096 MB。难度为 BEGINNER / INTERMEDIATE / ADVANCED，发布状态为 DRAFT / PUBLISHED / DISABLED。

镜像上传示例（在已经部署的平台上）：

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F 'display_name=SQL Injection Target' \
  -F 'file=@sqli-basic.tar;type=application/x-tar' \
  http://localhost:8080/api/admin/images/upload
```

上传期间 `size_bytes` 为上传字节数，READY 后以 Docker 返回的镜像大小为准。`original_filename` 仅用于展示，实际临时文件名始终为 UUID。不要使用原文件名拼接服务器路径。

删除仍被引用的镜像：

```json
{
  "error": {
    "code": "IMAGE_IN_USE",
    "message": "镜像仍被实验模板引用，请先解除关联"
  }
}
```

## 私有编排接口

仅位于 `lab-control-net`，Nginx 不转发，也不发布宿主机端口：

- `DELETE /internal/images/{id}`：校验控制服务密钥后执行镜像引用检查与删除。
- `WS /internal/sessions/{id}/desktop`：同时校验控制服务密钥和桌面票据，仅开放固定 VNC 转发。
- `GET /health`：私有服务存活检查。

学生实验创建/重置/停止命令直接持久化在数据库，编排器后台处理，不依赖 HTTP BackgroundTasks 的进程内队列。
