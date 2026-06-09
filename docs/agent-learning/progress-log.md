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

### Phase 0 进展

- 已在 `my_agent/` 下创建最小 CLI agent 骨架。
- 已建立 `my_agent/.env` 与 `my_agent/.env.example` 配置路径。
- 当前主链路已经固定为：
  - `app.py -> AgentLoop -> ContextBuilder -> AgentRunner -> StubProvider`
- `SessionManager` 当前为内存态实现，先服务于 Phase 0 的单次链路打通。
- 已添加最小测试，覆盖：
  - 核心模块可导入
  - `AgentLoop` 能返回 stub reply 并写入历史
  - `Settings` 能从 `.env` 读取配置
  - `build_app()` 能完成依赖装配

### 推荐断点

- `my_agent/app.py`
- `my_agent/agent/loop.py`
- `my_agent/agent/context.py`
- `my_agent/agent/runner.py`
- `my_agent/agent/provider.py`
- `my_agent/session/manager.py`

### 下一步

- 进入 `Phase 1`
- 把 `StubProvider` 替换为真实 OpenAI-compatible provider 调用
- 保持当前分层不变，只补单轮对话能力

## 2026-06-09

### Phase 1 进展

- `my_agent` 已从 `StubProvider` 切换为真实的 OpenAI-compatible provider。
- 当前 provider 走的是最小单轮链路：
  - `client.chat.completions.create(model=..., messages=...)`
- `build_app()` 现在负责把 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL` 注入 provider。
- `AgentRunner` 的职责没有变化，仍然只是：
  - 接收 `messages`
  - 调用 provider
  - 返回模型文本

### 当前理解

- `ProviderAdapter` 这一层的价值，在于把“HTTP/API 细节”隔离出去。
- `AgentLoop` 不应该知道 base_url、api_key、model 这些 provider 细节。
- `ContextBuilder` 负责“组 messages”，`AgentRunner` 负责“跑模型”，这两个边界是清晰的。

### 已完成验证

- `pytest tests/my_agent/test_phase0.py tests/my_agent/test_phase1.py -v` 通过。
- `python -m my_agent.app` 已完成真实接口冒烟，CLI 可以返回模型回复。

### 下一步

- 进入 `Phase 2`
- 把当前 session 的历史真正用于第二轮对话
- 验证第二轮提问时，模型能够引用上一轮上下文
