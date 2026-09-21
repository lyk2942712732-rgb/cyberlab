# Linux 验收清单

本文件是待执行清单。当前交付按用户要求只写代码，没有在 Windows 部署或执行任何以下步骤；各项都不代表已经通过。

## 准备

- [ ] 在独立 Linux 环境安装 Docker Engine 28+ 和 Compose 2.24.4+。
- [ ] 用 `scripts/init_env.py` 生成唯一密钥与密码，准备 `/var/lib/cyberlab` 权限。
- [ ] 构建系统 Kali；准备外部 `docker save` 靶机 tar。
- [ ] 启动 Compose，确认迁移成功、PostgreSQL/Redis/Backend/Orchestrator 就绪。
- [ ] 执行种子数据，按 README 设置 HTTPS 或开发 SSH 转发。
- [ ] 分别运行后端 pytest、前端 TypeScript 构建、浏览器用例，记录真实结果。

## 完整业务链路

- [ ] admin 登录，仅显示统一教学管理端。
- [ ] 上传 tar，观察 IMPORTING → READY、repo/tag/image_id/size/digest/原文件名；确认临时 tar 已移除。
- [ ] 在 Docker Engine 中确认镜像存在，平台没有构建过上传的靶机。
- [ ] 创建课程、章节与 Markdown 课时，设置发布状态和关联实验。
- [ ] 创建 Lab Template，明确填写内部端口、时间、CPU、内存及 Flag。
- [ ] student01 登录，学习课时并确认进度持久化。
- [ ] 启动实验，HTTP 快速返回 202，重复点击不产生第二个活动 Session。
- [ ] 后台创建恰好两台容器与一个独立内部网络；Target 使用保存的 Image ID。
- [ ] 页面显示 Target IP、端口、倒计时和真实 Kali 图形桌面。
- [ ] 在 Kali 内访问 Target 指定端口并完成实验。
- [ ] 错误 Flag 得 0 分且记录尝试；正确 Flag 得 100 分；后续错误不回退已得成绩。
- [ ] 学生和教学管理端均能看到完成情况、首次完成时间、提交次数。
- [ ] Reset 创建新容器/网络，旧容器/网络消失，截止时间不变。
- [ ] End 或 TTL 到期后两台容器与网络消失，镜像、模板和成绩保留。

## 网络与权限（必须在实际主机验证）

创建两个学生的实验，分别记录其容器、网络和靶机 IP。可由运维通过 Docker inspect 查看资源，但学生页面不能访问 Docker API。

- [ ] Kali A → Target A 指定端口可访问。
- [ ] Kali A → Kali B / Target B 不可访问；反向同样不可访问。
- [ ] Target → PostgreSQL / Redis / Backend / Orchestrator 不可访问。
- [ ] 实验网络不能访问宿主机网关服务或公网；DNS 不能借宿主机进行外部解析。
- [ ] `docker inspect` 显示实验容器只有一个实验网络，没有 HostConfig.Privileged、host network、敏感 Bind、Socket 或设备。
- [ ] CPU、内存、PIDs 与日志限制确实生效。
- [ ] VNC 5901 与 websockify 6080 仅绑定 Kali loopback，宿主机没有对应发布端口。
- [ ] 学生 B 查询、重置、停止、提交学生 A Session 均被拒绝。
- [ ] 学生访问 `/admin/*` 被拒绝；公共实验接口和错误响应不泄露正确 Flag。
- [ ] Markdown 中脚本、事件处理器和 iframe 不执行。
- [ ] 桌面票据过期、重放、跨 Session、跨用户或跨 Origin 均无法建立桌面连接。
- [ ] 已连接桌面在 Stop / Reset / TTL 后被主动断开。

## 镜像与异常恢复

- [ ] 非 tar、伪 MIME、缺少 Docker 清单、空包、多镜像包、超大文件均得到明确错误并清理临时文件。
- [ ] load 失败记录 ERROR 与错误说明，列表不包含宿主机敏感错误细节。
- [ ] 本地镜像缺少 repo_digest 时仍可使用，页面显示为空/无仓库摘要。
- [ ] 再上传同名 tag 的新镜像后，旧模板仍以原 Image ID 创建 Target。
- [ ] 同一 Image ID 重复上传提示使用已有镜像，不产生两个 READY 资产。
- [ ] 被模板或运行/停止容器使用的镜像删除返回 IMAGE_IN_USE，镜像和记录仍在。
- [ ] 无引用镜像通过 Docker API 非强制删除，再删除数据库记录。
- [ ] Kali/Target 镜像缺失、目标端口错误、容器启动失败均不会遗留可用状态或无限容器。
- [ ] 停止编排器、恢复后能够处理之前的 CREATING / RESETTING / STOPPING 和已到期 Session。
- [ ] 在容器创建与数据库提交之间终止编排进程，恢复后可通过标签清理残留。
- [ ] Docker 服务不可用时清理保留待重试状态；恢复后回收成功。
- [ ] 两个并发启动请求、模板编辑与启动竞态、模板关联与镜像删除竞态在真实 PostgreSQL 下验证。

## 待填写的验收记录

```text
Linux / Docker / Compose 版本：
Git commit 或代码归档版本：
Kali / Target Image ID：
后端 pytest 结果：
前端构建结果：
浏览器测试结果：
网络隔离结果：
完整链路结果：
已知问题及修复记录：
验收时间与人员：
```
