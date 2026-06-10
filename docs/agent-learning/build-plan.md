# my_agent 演进路线图

## 目标

把 `my_agent` 从“最小 CLI 同构版”推进成“以 `nanobot` 为参考架构的完整 agent 框架”。

当前已经完成第一阶段：把这条最小主链路亲手做对：

`user input -> AgentLoop -> ContextBuilder -> AgentRunner -> ToolRegistry -> SessionManager -> output`

接下来进入第二阶段，目标不再是证明骨架成立，而是围绕这个骨架逐步补齐产品级能力。

## 范围控制

### 第一阶段已完成

- CLI 单用户入口
- OpenAI-compatible provider
- 多轮历史
- 基础工具调用
- 本地 session 持久化

### 第一阶段刻意未做

- WebUI
- 多渠道
- MCP
- cron
- subagent
- 长期记忆
- 图片、多模态
- 复杂权限系统

### 第二阶段要做什么

- 扩展常用工具体系
- 建立统一入口抽象
- 补强 provider / runtime / observability
- 逐步引入 memory、压缩、恢复等运行时能力
- 为多渠道、MCP、subagent 预留演进路径

### 第二阶段暂不追求什么

- 一次性追平 `nanobot` 全部能力
- 为了功能数量破坏当前分层边界
- 未经定位确认就直接堆平台适配或生态集成

## 分阶段计划

### 第一阶段（已完成）：最小同构版

目标：

- 固化最小核心主链路
- 学清楚 `nanobot` 的本质复杂度
- 验证 `AgentLoop / AgentRunner / ToolRegistry / SessionManager` 的边界

已完成范围：

- `agent/loop.py`
- `agent/runner.py`
- `agent/context.py`
- `agent/provider.py`
- `tools/base.py`
- `tools/registry.py`
- `session/manager.py`
- `app.py`

完成结果：

- 已完成 `Phase 0-6`
- 已能解释 `my_agent` 与 `nanobot` 各核心层的异同
- 已确认 `my_agent` 可以从“学习项目”升级为“完整 agent 框架起始版本”

### 第二阶段 Phase A：重新定义项目定位与边界

目标：

- 明确 `my_agent` 不再只是最小 CLI 项目
- 固化“完整 agent 框架”的目标表述
- 区分哪些能力属于当前阶段的主线，哪些属于后续生态扩展

完成标准：

- 文档中的项目定位、当前状态、后续路线不再停留在“最小 agent”
- 新会话中的 agent 可以直接读文档理解当前真实阶段

### 第二阶段 Phase B：扩展常用工具体系

目标：

- 恢复并扩展 coding / agent 常用工具
- 把工具分层从“最小闭环”推进到“可持续开发”
- 为后续 Web、MCP、subagent 奠定稳定 registry 形态

优先级建议：

- 第一批：`read_file`、`list_dir`、`exec`
- 第二批：`write_file`、`edit_file`、`find_files`、`grep`、`apply_patch`
- 第三批：`write_stdin`、`list_exec_sessions`
- 第四批：`web_search`、`web_fetch`

完成标准：

- `ToolRegistry` 能承载比最小闭环更多的开发期常用工具
- 日常 coding / inspection / patching 工作不再依赖手工 shell 兜底

### 第二阶段 Phase C：统一入口与接口层

目标：

- 让 `my_agent` 不再只等同于 CLI
- 抽出统一消息入口模型
- 为 API / WebUI / 多渠道适配预留稳定边界

候选方向：

- CLI
- OpenAI-compatible API
- WebUI
- 多渠道 chat adapter

完成标准：

- 即使入口增多，`AgentLoop -> AgentRunner` 主链路仍保持稳定
- 入口层复杂度不会泄漏进工具、session、provider 核心层

### 第二阶段 Phase D：运行时能力与可观测性

目标：

- 让 agent 执行过程对开发者可见
- 继续增强日志、状态恢复、执行会话、错误边界
- 降低“运行像盲盒”的不确定性

完成标准：

- 能看见每轮输入、上下文摘要、工具调用、最终回复摘要
- 长命令与多轮执行具备可观察状态
- 错误信息对开发者调试友好

### 第二阶段 Phase E：记忆、压缩与恢复

目标：

- 从“能保存历史”推进到“能管理历史”
- 逐步引入摘要、归档、恢复、上下文裁剪等能力
- 接近 `nanobot` 在长期运行场景下的运行时形态

完成标准：

- 长期使用时不会因为上下文无限增长而失控
- 关键状态在重启后仍可恢复
- 历史不会污染模型的有效上下文

### 第二阶段 Phase F：产品级扩展层

目标：

- 在核心层稳固后，再引入：
  - 多渠道
  - MCP
  - cron
  - subagent
  - image / multimodal
  - 更完整的 provider 能力

完成标准：

- `my_agent` 从“完整 agent 框架起始版本”进入“可扩展产品化 agent”
- 新能力建立在已经稳定的主链路与工具/runtime 基座之上

## 开发原则

1. 核心主链路优先稳定，扩展能力不要反向污染内核。
2. 每次只推进一个清晰主题，不做“顺手多加几个能力”的发散式开发。
3. 第二阶段的工作目标是产品能力扩展，不再是最小骨架补课。
4. 任何新能力都要能明确回答：它属于核心层、运行时层，还是扩展生态层。

## 每阶段固定输出

每完成一个阶段，都要留下 3 种产物：

- 可运行代码
- 1-2 个最小测试
- 一段“我现在理解了什么”的总结

## 后续协作方式

后面每次正式开工，都按这个格式推进：

1. 先选一个 phase
2. 我给出该 phase 的最小文件清单和目标
3. 你写代码或我帮你改代码
4. 我们一起调试
5. 回写 `progress-log.md`

## 当前推荐起点（已更新）

下一步不再从 `Phase 0` 重来，而是从第二阶段开始，优先做下面两件事之一：

- `Phase A`：把项目定位和后续边界彻底文档化
- `Phase B`：恢复并扩展常用工具体系

原因：

- 第一阶段最小骨架已经完成，不需要再重复“证明主链路成立”
- 当前最大的风险不是不会写代码，而是定位不清导致后续扩展发散
- 工具体系是从“能跑”走向“能用”的第一块产品化基石
