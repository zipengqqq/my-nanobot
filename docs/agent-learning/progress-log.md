# Agent 学习进度日志

## 2026-06-08

### 决策

- 不直接硬啃整个 `nanobot` 源码作为主要学习方式。
- 改为“以 `nanobot` 为参考架构，亲手实现最小 CLI 同构版”。
- 后续多轮对话中的架构结论，以本目录下文档为准，而不是依赖聊天上下文记忆。

### 当前理解

- `nanobot` 的核心不是“很多工具”，而是“消息编排层”和“推理循环层”的分离。
- `AgentLoop` 负责一轮 turn 的编排。
- `AgentRunner` 负责一轮 LLM + tools 的执行循环。
- `ContextBuilder`、`ToolRegistry`、`SessionManager` 都是在给这条主链路提供支持。

### 当前范围

第一阶段只做最小 CLI agent，保留这些层：

- `AgentLoop`
- `ContextBuilder`
- `AgentRunner`
- `ToolRegistry`
- `SessionManager`
- `ProviderAdapter`

暂不实现：

- 多渠道
- WebUI
- MCP
- cron
- subagent
- 长期记忆

### 下一步

- 进入 `Phase 0`
- 创建最小项目骨架
- 先把目录和类关系搭出来，再逐步填实现
