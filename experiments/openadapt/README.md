# OpenAdapt Capture / Kali 试录

独立技术验证，不启用学生录制，不修改正式 `cyberlab/kali:local` 镜像或实验启动流程。
脚本通过 XTest 向真实应用发送输入，由 OpenAdapt 原生采集器产生数据库和视频。
这是**自动化桌面实录**，不是学生或真人操作样本，也不是直接写入数据库的合成 fixture。

## 安装边界

- Ubuntu 上的独立容器 `cyberlab-openadapt-pilot`，镜像 `cyberlab/kali:openadapt-pilot`。
- 采集器与 XFCE、终端、Firefox、Burp 同在 Kali 内部，连接 `DISPLAY=:1` 和 XFCE 的 D-Bus 会话。
- 无对外端口、无外部网络、无 Docker socket；2 CPU / 1536 MiB / 512 PID / 256 MiB shm，关闭 swap，沿用实验容器的 capability 限制。
- `/evidence` 挂载到宿主机的专用目录，停止或删除测试容器不会删除数据。
- 关闭音频、浏览器扩展、远程上传；5 FPS。仅操作测试命令、本地测试网页和 Burp 界面。

## 版本

2026-09-23 核查 PyPI 最新为 1.2.2，GitHub 主分支标记为 1.3.0。
Linux AT-SPI 和新录制控制接口不能按 PyPI 1.2.2 的能力来描述。本次安装固定源码快照，
不宣称这是正式发布的 1.3.0：

- 提交：`986ebaeae6700c58b0e523b54471ce8d3ef01925`
- 源码包：<https://codeload.github.com/OpenAdaptAI/openadapt-capture/tar.gz/986ebaeae6700c58b0e523b54471ce8d3ef01925>
- SHA256：`d1ce1c84e7d93a23a3a6b2b8939fe3a7badff3feebf94040ec51d045deb60e13`
- 隔离 venv：`/opt/openadapt`；使用 Kali 的系统 `python3-gi` 和 `gir1.2-atspi-2.0`，
  而不是编译 upstream `[linux]` extra 锁定的旧 PyGObject。
- 实际 Python 依赖清单：镜像内 `/opt/openadapt-requirements.txt`。
- 本地补丁 `xrecord-create-sync-v1`：原版在 TigerVNC 上发生 `XRecordBadContext`。
  在控制连接创建 XRecord context 后调用 `XSync`，再由数据连接启用，避免跨连接请求顺序竞争。
  `patch_xrecord.py` 校验精确源码后才修改。测试结果必须注明包含此补丁。
- `native-receipt-forwarding-v1` 转发完成状态和失败，并释放隐私保留句柄；
  `xrecord-data-close-v1` 规避测试环境中 XCloseDisplay 阻塞。两者均校验固定源码，
  仍未使本轮完整性验证通过。
- 试录脚本为 Python 3.14 的 forkserver 预加载录制模块，减少多进程重复导入。
  使用 MPEG-4 / yuv420p 视频和原始 PNG 画面；原默认无损 H.264 `veryslow` 在该小型 VM 上开销较大。

源码提交和压缩包已固定；Kali rolling、apt 和 Python 间接依赖仍会变化，不能保证未来重建逐字节一致。

## 重现

先准备已有正式 Kali 镜像。以下操作在 Ubuntu 上执行，目录参数使用绝对路径。

```sh
pilot_dir=/home/yukuan/cyberlab/.deploy/openadapt-pilot
mkdir -p "$pilot_dir/build" "$pilot_dir/evidence"
cp experiments/openadapt/Dockerfile "$pilot_dir/build/"
cp experiments/openadapt/patch_xrecord.py "$pilot_dir/build/"
cp experiments/openadapt/patch_receipts.py experiments/openadapt/patch_xrecord_close.py "$pilot_dir/build/"
cp experiments/openadapt/probe.py experiments/openadapt/export.py experiments/openadapt/start-pilot.sh "$pilot_dir/"
curl --fail --location \
  https://codeload.github.com/OpenAdaptAI/openadapt-capture/tar.gz/986ebaeae6700c58b0e523b54471ce8d3ef01925 \
  --output "$pilot_dir/build/openadapt-capture.tar.gz"
docker build --pull=false -t cyberlab/kali:openadapt-pilot "$pilot_dir/build"
sh "$pilot_dir/start-pilot.sh" "$pilot_dir"
docker exec cyberlab-openadapt-pilot python3 /opt/pilot/probe.py terminal /evidence/terminal-01
docker exec cyberlab-openadapt-pilot python3 /opt/pilot/export.py /evidence/terminal-01
```

`probe.py` 第一个参数可用 `terminal`、`firefox`、`burp`。每次指定一个**不存在**的输出目录，
防止覆盖证据。逐个测试，避免同时启动 Firefox 和 Burp。该脚本不接受已有学生容器作为参数。
首次运行可能暴露依赖或应用兼容性问题，失败的录制必须保留并标记失败，不能视为有效证据。

## 输出

每次测试包含：

- `capture/`：OpenAdapt 原生数据库、MP4、状态及完整性元数据（仅成功完整收尾时有完整文件）。
- `application.log`、`result.png`：应用诊断和操作后的画面。
- `resources.json`：容器级 CPU、内存及 PID 采样；包括应用、桌面、录制器、缓存和收尾开销。
- `export/raw-events.jsonl`：原生事件模型序列化。
- `export/actions.jsonl`：官方处理器合并后的动作，剔除重复的子事件；保留结构信息和画面时间引用。
- `export/summary.json`：数量、类型、文本序列、控件样本、视频信息、资源统计。
- `export/action-before.png`：由官方接口读取的一次动作前画面。

导出器先使用 `CaptureSession.load_verified()` 验证完整性，再以只读方式读取数据库。
所有派生文件放在 `capture/` 外，避免破坏原始完整性封装。字段缺失时保留空值，
不推断按钮名称、命令是否执行成功、学生意图或实验得分。

## 正式接入前

### 当前验证结论（2026-09-24）

本轮 Ubuntu/TigerVNC 验证仍未通过正式接入门槛。native-receipt-forwarding-v1 修复了上游隐私收据包装缺少 finished 状态的问题，试录可以启动并写入画面与动作行；但 X RECORD 在停止时没有交付 EndOfData，OpenAdapt 因而将会话保持在 phase=finalizing、complete=false、integrity_verified=false。这不是可用于学生行为分析的完整记录，不能将 cyberlab/kali:openadapt-pilot 标记为正式镜像，也不能接入正式实验生命周期。patch_xrecord_close.py 只避免了已观察到的 XCloseDisplay 阻塞，不能绕过完整性检查，因此当前仍保留为试验代码。

短时试录只能证明这些应用和操作在当前镜像上的表现。仍需评估长时间运行、并发学生、
录制中桌面分辨率变化、磁盘配额、异常退出、会话隔离、敏感输入排除及数据保留规则。
尤其是无障碍控件缺失时，需要画面或应用自身日志补充，不能承诺每个程序都能输出完整语义。

测试结束后停止专用容器即可释放资源：

```sh
docker stop cyberlab-openadapt-pilot
```

试验失败时只保留宿主机 evidence 目录供复查；删除带 cyberlab.experiment=openadapt-pilot 标签的测试容器和 cyberlab/kali:openadapt-pilot 镜像。不要把录制文件、用户 profile 或完整原始日志提交到 Git。
当前基础镜像的桌面启动脚本在强制停止后可能遗留 X11 锁文件；此时应重建专用测试容器，
不要将 `docker restart` 视为一定可恢复。宿主机 evidence 目录不受容器重建影响。
