# 软件供应链与来源验证 · 参考解答

## 目标与实现边界

这是一个**纯数据模拟**的主题安装器。它不会下载外部包，也不会运行任意安装脚本。目标是观察：安装器接受来源参数，却没有把“可信发布者/可信来源”变成必须满足的安全条件。

## 复现步骤

1. 访问 `/registry`。同名组件 `lesson-theme` 在 official 中是版本 1.0、发布者 course-team、trusted=true；community 中是版本 9.9、发布者 unknown、trusted=false。
2. 用首页表单安装 `source=official`、`package=lesson-theme`，预期“已安装官方主题”，没有 Flag。
3. 保持包名不变，只把 source 改为 `community` 再安装。预期显示未验证发布者的组件执行了**模拟**安装钩子，并返回教学凭据中的 Flag。
4. 保存两种来源的对照结果，提交 Flag。

```bash
TARGET='http://TARGET_IP:8000'
curl -sS "$TARGET/registry"
curl -sS "$TARGET/install" --data-urlencode 'source=official' --data-urlencode 'package=lesson-theme'
curl -sS "$TARGET/install" --data-urlencode 'source=community' --data-urlencode 'package=lesson-theme'
```

## 预期现象与常见误区

安装接口需要 POST，curl 使用 `--data-urlencode` 后会采用 POST。错误包名或来源会返回 404；不能用它们证明信任校验正确。更高版本号是选择诱因，不是安全证明；此场景并没有自动比较版本或自动选择 9.9，实际触发的是提交了未被拒绝的 community 来源。

不要把返回的模拟说明误写成“已在服务器任意执行代码”或“已攻破真实包仓库”。本实验验证的是安装器的信任决策，未覆盖构建服务器入侵或真实包签名链。

## 修复思路与回归

固定允许的仓库、组件及版本；验证可信发布者、签名和来自可信渠道的摘要；限制构建凭据能读取的资源。单独计算下载包的哈希并不能证明其可信，攻击者也能为恶意包提供自己的哈希。

回归应保证：已批准来源的正确组件仍可安装；同名但未知来源的组件在任何安装钩子之前被拒绝；篡改包或签名失败时不继续安装；有必要的审计结果，但日志不记录凭据。

## 本实验评估要点

核实 official 与 community 的身份/信任差别及安装结果对照，说明“名字相同或版本更高不代表来源可信”。允许表单或 HTTP 工具。只有拿到 Flag 而将过程描述为真实远程代码执行，不满足对本教学边界的准确解释。
