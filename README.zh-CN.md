# PersonalMemoryOS

根据用户纠正更新偏好，跨 session 读取，按场景应用，每次变更由 Git 保存。

[English](README.md) · [接入方法](docs/integrations.md) · [设计与例子](docs/design.md) · [研究依据](docs/evidence.md)

这是一个小型、本地优先的 agent 记忆系统。Codex、Claude Code 可以通过相同的 CLI 或 MCP 工具共享一个私有 Git 记忆仓库。用户正常反馈“以后应该这样做”，由 agent 提炼为有适用范围的规则；底层负责持久化、并发冲突检查、重试去重和回滚。

当前是 **0.1 alpha**：核心存储、CLI、并发和 hook 协议有自动测试。自然语言反馈由宿主 agent 理解，skill 和 hook 提供更新流程。尚未做真实模型的跨 harness 遵循率实验，也未提供可直接连接网页 ChatGPT 的远程认证服务。

## 开始使用

```bash
git clone https://github.com/tongmd/personalmemoryos.git
cd personalmemoryos
python3 -m venv .venv
.venv/bin/pip install -e '.[mcp]'
.venv/bin/pmos init
.venv/bin/python examples/demo.py
```

源代码仓库与个人记忆仓库分开。默认记忆保存在 `~/.personalmemoryos`，不会自动上传，也不会自动配置 Git remote。

连接 harness 后，日常只需正常表达：

| 输入 | 应有行为 |
|---|---|
| “以后研究评估都给一手资料和实验数据。” | 更新研究场景的已有规则，保留反馈来源并提交 Git。 |
| “这次详细解释。” | 本轮生效，不覆盖长期默认。 |
| “你又没按上次要求做。” | 检查规则是否加载、是否执行；已有正确规则不重复追加。 |
| “查看研究场景的记忆。” | 返回当前有效规则与版本。 |
| “撤销刚才的更新。” | 产生新的撤销提交，下一轮加载撤销后的状态。 |

hook 负责每轮加载和反馈学习指引，MCP 工具负责读写；需要两者一起接入，才能形成完整流程。模型是否正确识别反馈和遵循规则仍需实际评测。

## 文件与冲突

采用一个短索引，加上按场景组织的规则文件：全局、研究、编程、写作、项目规则可以分开。每条规则使用稳定 ID，记录内容、适用范围、项目、来源和时间。不同场景不会仅因为措辞相反就互相覆盖。

多个本机 harness 通过相同写入口修改一个仓库：

- 不同规则的并发更新可自动合并。
- 同一条规则被其他 session 改过时，返回冲突，要求 agent 读取新版本后判断。
- 每轮从一个固定 Git commit 读取，避免多个文件混用新旧版本。
- 回滚保留反馈处理记录，旧请求重试不会让已撤销规则重新生效。
- 语义上相互矛盾、但 ID 不同的规则仍由 agent 判断；底层不假装能自动理解全部自然语言冲突。

初版支持 macOS/Linux、Python 3.11+、Git。核心无第三方运行时依赖；MCP 为可选依赖。跨设备服务、远程认证和网页 ChatGPT 接入尚在后续范围。

已有论文支持“反馈更新持久记忆能够改善后续任务”，但本文引用的论文数据属于各自系统，不能当作本项目的实验结果。具体来源和限制见[研究依据](docs/evidence.md)。

## 验证

```bash
.venv/bin/pip install -e '.[dev,mcp]'
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python examples/demo.py
```

要验证“真的遵循”，应在新 session 中比较无记忆、固定记忆和反馈更新三种模式，测同类错误复发率、正确应用率、跨场景误用率和延迟。测试方案见[行为验证](docs/evaluation.md)。

MIT 开源。个人记忆与历史反馈请保存在私有仓库；忘记或回滚有效规则不会删除 Git 历史中的旧内容。
