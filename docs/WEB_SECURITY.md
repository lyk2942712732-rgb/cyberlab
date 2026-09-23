# Web 安全课程包与实验资源监控

以 [OWASP Top 10:2025](https://top10.owasp.org/2025/) 的十个风险类别为框架，提供 4 门新增课程、12 个课时及 12 个独立实验。Top 10 是风险分类，不是十种具体漏洞的固定清单；本课程用代表性场景讲解每类风险，并增加 XSS、SSRF 专项。

| 镜像场景 | 分类 | 实验 |
|---|---|---|
| access | A01 访问控制失效 | 订单对象越权 |
| config | A02 安全配置错误 | 备份与调试配置泄露 |
| supply | A03 软件供应链失效 | 同名组件来源验证缺失（本地数据模拟） |
| crypto | A04 密码学失效 | 将 Base64 当成加密 |
| sqli | A05 注入 | 登录 SQL 注入 |
| design | A06 不安全设计 | 优惠券重复核销 |
| auth | A07 认证失效 | 账户恢复未验证身份 |
| integrity | A08 软件或数据完整性失效 | 未签名角色令牌 |
| logging | A09 安全日志与告警失效 | 连续失败未记录和告警 |
| exception | A10 异常条件处理失当 | 策略解析失败后放行 |
| xss | A05 专项 | 反射型 XSS |
| ssrf | A01 专项 | 预览器访问内部服务 |

每个实验均有单独的镜像配置和镜像 ID，共享基础镜像层以节省磁盘。运行时只启动学生选择的场景，使用独立网络与独立可写容器层；靶机上限为 0.5 核额度、128 MiB，Kali 仍使用部署环境已有设置。每个靶机由 `LAB_FLAG` 接收判题值。静态 Flag 是教学完成凭据，不能防止学生互相分享答案。

供应链实验使用本地组件元数据模拟安装钩子的影响，不运行任意安装脚本；SSRF 仅请求靶机的回环内部服务，不依赖互联网、云账号或额外容器。A09 同时包含短 PIN 的认证弱点，教学重点要求对比三次失败前后的日志和告警。

## 构建、上传与发布

在 Linux 开发/部署主机执行。平台仍只接受成品 tar 并执行 Docker load，不在上传接口中构建镜像。

```bash
python3 scripts/build-web-security.py
# 如已有兼容的 Python 3.12 Alpine 教学镜像，可以使用 --base-image 指定它。
```

输出为 `dist/web-security/` 中的 12 个 tar 与 manifest.json。管理员可在管理页面逐个上传；也可使用后端依赖环境中的批量上传脚本（密码从环境读取）：

```bash
# 在能够访问平台 API 且安装了 httpx 的环境中运行
python scripts/import-web-security.py --url http://backend:8000 --image-dir /path/to/web-security
```

脚本通过管理员登录与上传接口导入，等待 READY 并校验镜像 ID；重复运行复用已有 READY 镜像，不重复创建目录记录。它输出 `image-map.json`，将该文件传入后端容器后执行：

```bash
python -m app.seed_web_security --image-map /tmp/image-map.json
```

初始化器先检查完整的 12 镜像映射，再在一个数据库事务内创建内容；重复运行保留教师对现有同名课程、课时和实验的编辑，不改变已有账号、成绩、学习进度或活动实验。更新已有实验镜像时使用管理界面显式编辑，不依赖重复初始化覆盖。

## 资源监控

学生在实验页展开「资源与健康状态」后采样 Kali 和靶机，每 5 秒更新。收起、离开页面、页面隐藏、实验重置或终止时停止轮询并取消正在等待的前端请求。已发出的 Docker 读取可能继续至超时。

- CPU 100% 表示一个虚拟 CPU 的使用量；另显示相对容器额度的比例。首次采样没有差分基准，显示「采样中」。
- 内存使用量扣除 inactive file cache，同时显示限制与占比。
- 网络提供累计收发量和两次采样间速率；另显示进程/线程数量、上限和运行时间。
- 运行状态与 Docker HEALTHCHECK 状态分开展示；没有 HEALTHCHECK 时显示「未配置健康检查」，不假定健康。
- 失败只在面板内提示，不反复弹窗；旧采样显示时间与淡化效果。
- 仅会话所有者和管理员可查询；后端通过私有编排器接口读取指标，Docker 再校验管理标签和会话标签，不返回环境变量、宿主机进程或健康检查日志。

接口：`GET /api/lab-sessions/{id}/metrics`。数据包含 `sampled_at`、`interval_seconds` 和 `instances`。编排器按会话、代次和实例集合缓存 5 秒，历史计数器在 60 秒后失效，不启动持续后台采集。

## 验证

```bash
cd backend && python -m pytest -q
cd ../docker/targets/web-top10 && python -m unittest -v
cd ../../../frontend && npm run build
CYBERLAB_E2E_URL=http://127.0.0.1:4173 npx playwright test e2e/resources.spec.ts
```

资源面板测试使用明确的模拟 API，验证暂停轮询、采样错误、健康状态和窄屏布局；真实部署仍需验证管理员上传、学习关联、实验启动、两次真实 Docker 采样、Flag 判题和实验清理。XSS 的浏览器执行与 SSRF 的真实回环访问应单独验证，不能只把接口返回 200 当作完成。

### 2026-09-23 验证记录

以下检查在 Ubuntu 上执行，未在 Windows 上部署或运行测试：

- 后端 50 项测试通过，Ruff 检查通过；12 个场景的 13 项标准库测试通过。
- 前端类型检查、生产构建通过；Playwright 验证展开/收起、后台暂停、采样失败无弹窗及收起侧栏后的 390px 布局。
- 12 个独立镜像全部真实启动，Docker HEALTHCHECK 通过；逐一验证教学解题路径。SSRF 访问真实的靶机回环服务；测试容器无对外端口映射，验证后全部清理。
- 通过管理员 tar 上传接口导入全部镜像；发布 4 门新增课程、12 个课时与 12 个实验。连同原有 SQL 演示，当前共 5 门课程、13 个实验。
- 在线浏览器验证登录、课程/实验列表、真实资源面板、Kali 桌面显示与刷新重连；独立浏览器验证同一 XSS 靶机源码中的脚本执行及教学 Cookie 读取。
- 新 SQL 实验验证 Kali 到靶机的真实请求、错误与正确 Flag 判题、两次真实 Docker 资源采样，以及结束后容器、网络清理和监控已回收状态。
- Kali 配置仍为 2 核额度、1536 MiB、512 个进程/线程。TGA、其数据库与 Ubuntu 图形桌面服务保持运行。

部署前数据库快照保存于服务器 `.deploy/before-web2025.sql`；旧平台镜像保留为 `cyberlab/backend:before-web2025` 和 `cyberlab-frontend:before-web2025`。课程内容和镜像已经导入，回退前端/后端镜像不会自动删除新增教学数据。
