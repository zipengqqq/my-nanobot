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

### Phase 4 进展

- `AgentRunner` 已从单次 tool call 闭环扩展为真正的多轮 tool loop：
  - 每轮都先请求模型
  - 如果模型返回 tool call，就执行工具并继续下一轮
  - 如果模型返回最终文本，就结束本轮执行
- 已为 `AgentRunner` 增加 `max_iterations`，用于防止模型无限请求工具。
- 已新增 `RunnerResult`，把本轮最终文本和“本轮新增消息”一起返回给 `AgentLoop`。
- `AgentLoop` 现在会把一整轮真实消息写入 session：
  - `user`
  - `assistant`（tool call）
  - `tool`
  - `assistant`（最终文本）
- `ChatMessage` 已扩展为支持：
  - `tool_calls`
  - `tool_call_id`
- `ContextBuilder` 现在会把这些结构化字段重新还原成模型可消费的 message dict。
- `SessionManager` 已改为按 `user` 消息切分 turn，再保留最近 N 轮历史，不再假设“一轮只有 2 条消息”。
- `build_app()` 现在会把 `MY_AGENT_MAX_ITERATIONS` 注入 `AgentRunner`；未配置时默认值为 `6`。

### 当前理解

- `Phase 4` 的关键不是“多跑几次 provider”，而是把“循环执行”和“历史落盘”这两件事拆在正确的层里。
- `AgentRunner` 负责本轮循环里到底发生了哪些 assistant/tool 消息；`AgentLoop` 只负责把这些结果写进 session。
- 一旦进入 tool loop，历史裁剪就不能再按固定消息条数做，只能按 user turn 做切分，否则会把一轮对话截成半截。
- `max_iterations` 本质上是一个安全边界：它不是业务功能，但没有它，agent loop 就没有收敛保证。

### 已完成验证

- `pytest tests/my_agent/test_phase0.py tests/my_agent/test_phase1.py tests/my_agent/test_phase2.py tests/my_agent/test_phase3.py tests/my_agent/test_phase4.py -q` 通过。
- `tests/my_agent/test_phase4.py` 已覆盖：
  - 连续多次 tool call 后返回最终答案
  - assistant/tool 消息写入 session history
  - 超过 `max_iterations` 时中止 loop

### 下一步

- 进入 `Phase 5`
- 把当前内存态 session history 落到本地文件
- 重启 CLI 后恢复既有会话
- 开始区分“运行时状态”和“持久化状态”的边界

### Phase 5 进展

- `SessionManager` 已从纯内存态扩展为“内存缓存 + 本地文件持久化”：
  - 支持按 `session_id` 懒加载历史
  - 支持把 session 历史写入本地 JSON 文件
  - 仍然保持“按最近 N 轮 user turn 裁剪”的语义
- `ChatMessage` 已补齐序列化 / 反序列化能力，能够保留：
  - `role`
  - `content`
  - `tool_calls`
  - `tool_call_id`
- `build_app()` 现在会把 `MY_AGENT_SESSION_STORAGE_DIR` 注入 `SessionManager`。
- 默认 session 存储目录已固定为：
  - `my_agent/storage/sessions/`

### 当前理解

- `Phase 5` 的关键不是“把数据写到磁盘”这么简单，而是要保证“落盘后的历史仍然是可回放给模型的合法消息序列”。
- 一旦进入 `Phase 4` 的 tool loop，持久化层就必须完整保留 `assistant/tool` 结构化消息；否则重启后的 session 无法正确恢复上下文。
- `AgentLoop` 和 `AgentRunner` 在这一阶段不需要知道任何文件路径或 JSON 细节，说明当前分层仍然健康。

### 已完成验证

- `pytest tests/my_agent/test_phase5.py -q` 通过。
- `pytest tests/my_agent/test_phase0.py tests/my_agent/test_phase1.py tests/my_agent/test_phase2.py tests/my_agent/test_phase3.py tests/my_agent/test_phase4.py tests/my_agent/test_phase5.py -q` 通过。
- `tests/my_agent/test_phase5.py` 已覆盖：
  - tool loop 历史的持久化与重载
  - `build_app()` 重建后继续既有 session history

### 下一步

- 进入 `Phase 6`
- 把 `my_agent` 当前实现和 `nanobot` 原仓库逐层对照
- 明确哪些复杂度仍未进入最小实现：
  - skills / instruction loading
  - subagent / task orchestration
  - 长期 memory / compaction
  - MCP / 外部工具生态

### Phase 6 进展

- 已新增对照文档：
  - `docs/agent-learning/phase6-nanobot-comparison.md`
- 已把 `my_agent` 和 `nanobot` 按层逐一对照，覆盖：
  - 入口/装配层
  - `AgentLoop`
  - `ContextBuilder`
  - `AgentRunner`
  - `ToolRegistry`
  - `SessionManager`
  - `ProviderAdapter`

## 2026-06-10

### 入口层补充

- `my_agent/app.py` 已增加文件日志初始化能力。
- 运行 `app.py` 时，会在 `my_agent/` 目录下写入：
  - `my_nanobot.log`
- `my_agent` 的配置相关代码已改为目录化组织：
  - `my_agent/config/settings.py`
  - `my_agent/config/logger.py`
  - `my_agent/config/__init__.py`
- 原来的平铺文件已移除：
  - `my_agent/config.py`
  - `my_agent/logging_setup.py`
- 当前日志覆盖最小 CLI 入口事件：
  - 启动
  - 用户输入
  - assistant 回复
  - 退出原因（EOF / Ctrl+C / exit 命令）

### 当前理解

- 这次改动仍然属于入口/装配层补充，没有改变 `AgentLoop -> AgentRunner` 主链路。
- 现在配置与日志能力都通过 `my_agent.config` 包对外暴露，`app.py` 只保留装配和调用点。
- 日志调用方式已进一步收敛为直接使用 `logger` 单例，不再通过 `configure_logging` / `init_logger` 这类初始化函数进入。
- 即使模块移动到 `config/` 目录，`.env`、session 存储目录和 `my_nanobot.log` 仍然保持在 `my_agent/` 根目录语义下，没有发生路径漂移。

### 已完成验证

- `pytest tests/my_agent/test_app_logging.py -q` 通过。
- `pytest tests/my_agent/test_phase5.py -q` 通过。
- `pytest tests/my_agent/test_phase6.py -q` 通过。

### CLI 文案微调

- 当前工作仍然只触及 CLI 入口显示层，不涉及新的架构 phase。
- 已把 REPL 中 assistant 的输出前缀从 `助手>` 改为 `🐱>`。
- 启动文案继续保持：
  - `my_codex 已启动，输入quit或exit退出`

### 已完成验证

- 已新增最小回归测试，覆盖启动文案和 assistant 前缀：
  - `tests/my_agent/test_phase0.py::test_run_repl_prints_startup_banner_and_cat_reply`
- 已明确区分两类复杂度：
  - 本质复杂度：最小 agent 主链路本来就必须保留的骨架
  - 规模复杂度：产品化后才逐步长出来的能力与约束
- 已新增 `tests/my_agent/test_phase6.py`，用一个最小测试锁定关键边界：
  - `system prompt` 属于 `ContextBuilder`
  - session 历史不会错误持久化旧的 `system prompt`

### 当前理解

- 到 `Phase 6` 为止，`my_agent` 已经不只是“做出了一个能跑的 CLI agent”，而是已经能说明：
  - 哪些层是 `nanobot` 的核心骨架
  - 哪些复杂度只是因为 `nanobot` 需要支撑真实产品场景
- `AgentLoop -> ContextBuilder -> AgentRunner -> ToolRegistry -> SessionManager` 这条主链路，在 `my_agent` 中已经和 `nanobot` 保持同构关系。
- `nanobot` 真正难的地方，不是“文件更多”，而是：
  - 要保证更多运行时状态可恢复
  - 要保证更多工具与 provider 组合仍然合法
  - 要在更复杂的产品边界下维持同样的分层纪律

### 已完成验证

- `pytest tests/my_agent/test_phase6.py -q` 通过。
- `pytest tests/my_agent/test_phase0.py tests/my_agent/test_phase1.py tests/my_agent/test_phase2.py tests/my_agent/test_phase3.py tests/my_agent/test_phase4.py tests/my_agent/test_phase5.py tests/my_agent/test_phase6.py -q` 通过。

### 下一步

- 第一阶段的 0-6 个 phase 已完成。
- 如果继续第二阶段，不要默认“继续堆功能”，而要先选一个明确主题，例如：
  - 更完整的 provider 响应能力
  - 更严格的工具参数校验
  - 更接近 `nanobot` 的 history/token 裁剪
  - 受控引入 memory / skills / MCP 中的一层
