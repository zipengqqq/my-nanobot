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

### Phase 2 进展

- 已新增 `tests/my_agent/test_phase2.py`，覆盖两类关键行为：
  - 第二轮请求会带上第一轮的 `user/assistant` 历史
  - `SessionManager.history_limit` 按“最近 N 轮”而不是“最近 N 条消息”裁剪
- 已修正 `SessionManager` 的裁剪逻辑：
  - 当前 Phase 2 语义下，每轮按 2 条消息（`user` + `assistant`）计算
  - `history_limit=2` 时，会保留最近 2 轮共 4 条消息

### 当前理解

- “支持多轮历史”不只是把消息存起来，还要保证历史窗口的裁剪单位正确。
- 如果把 `history_limit` 当成消息条数，第二轮以上的上下文会被过早截断，实际效果会偏离 `build-plan.md` 里定义的“最近 N 轮历史”。
- 到 Phase 2 为止，`AgentLoop -> ContextBuilder -> AgentRunner -> SessionManager` 的边界仍然保持清晰，没有把历史裁剪逻辑泄漏到其他层。

### 已完成验证

- `pytest tests/my_agent/test_phase0.py tests/my_agent/test_phase1.py tests/my_agent/test_phase2.py -q` 通过。

### 下一步

- 进入 `Phase 3`
- 定义 `Tool` 抽象与 `ToolRegistry` 的最小可用形态
- 先接入 `read_file`、`list_dir`、`exec` 三个工具中的最小闭环

### Phase 3 进展

- 已扩展 `ToolSchema`，现在工具除了 `name`、`description` 之外，还会暴露最小参数 schema。
- 已实现 `ToolRegistry` 的最小可用闭环：
  - 注册工具
  - 输出 OpenAI-compatible tool schema
  - 按名称执行工具
  - 用统一 `ERROR: ...` 格式返回未注册工具或执行异常
- 已接入 3 个默认工具：
  - `read_file`
  - `list_dir`
  - `exec`
- `build_app()` 现在会默认装配这 3 个工具。
- `AgentRunner` 已从“单次纯文本调用”升级为“单次工具调用闭环”：
  - 第一次请求模型
  - 如果模型请求一个工具，就交给 `ToolRegistry` 执行
  - 把 tool call 与 tool result 回填进 messages
  - 再请求一次模型并返回最终文本

### 当前理解

- `Phase 3` 的重点不是“工具越多越好”，而是先把“schema 暴露”和“运行时分发”分开。
- 模型侧看到的是 tool schema，运行时真正执行的是 `ToolRegistry.execute()`，这两个视角必须明确拆开。
- 工具错误不能直接把 Python 异常泄漏出去，至少要先标准化成统一文本结果，这样模型下一跳才能继续消费。
- 当前 `AgentRunner` 只支持单次 tool call 闭环；连续多次工具调用和迭代上限控制，留到 `Phase 4` 再做。

### 已完成验证

- `pytest tests/my_agent/test_phase0.py tests/my_agent/test_phase1.py tests/my_agent/test_phase2.py tests/my_agent/test_phase3.py -q` 通过。
- `tests/my_agent/test_phase3.py` 已覆盖：
  - 单次 tool call -> tool result -> 最终回答
  - `ToolRegistry` 的标准化错误返回
  - `build_app()` 默认装配 3 个工具

### 下一步

- 进入 `Phase 4`
- 把当前单次工具调用分支扩展成真正的 tool loop
- 为 `AgentRunner` 增加最大迭代次数控制
- 开始考虑 assistant/tool 消息在最终历史中的保存边界
