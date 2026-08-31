# REPL 并行子 Agent 批次委派实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `my_agent` 终端 REPL 中实现主 Agent 按需拆分并行子任务、逐项进度提示、整批完成后一次汇总并持久化会话的能力。

**Architecture:** 保留同步的 `AgentLoop -> AgentRunner`。扩展现有 `SubagentManager` 为进程内批次协调器，使用有界线程池运行隔离子 Agent，并通过线程安全事件队列向 REPL 传递单项完成和整批完成事件。REPL 在前台轮结束后串行消费整批事件，将内部结果写入 `SessionManager` 并触发一次主 Agent 汇总轮。

**Tech Stack:** Python 3.11+、`concurrent.futures.ThreadPoolExecutor`、`queue.Queue`、现有 `AgentRunner`/`ToolRegistry`/`SessionManager`、pytest、ruff。

**Spec:** `docs/superpowers/specs/2026-08-31-repl-parallel-subagents-design.md`

## Global Constraints

- 默认最多并行三个子 Agent，可由 `MY_AGENT_MAX_CONCURRENT_SUBAGENTS` 配置。
- 仅修改 `my_agent/` 业务代码和回归测试；保留 REPL 为唯一产品入口。
- 子 Agent 不得递归委派，沿用现有工作区 Sandbox、路径允许目录和结果截断边界。
- 不记录密钥、完整工具原始输出或不必要的本地路径；使用 `pathlib.Path` 并保持 Windows 兼容。
- 修改后运行最接近变更的 pytest，并运行 `ruff check my_agent/`；不运行 `ruff format`。

---

### Task 1: 配置与批次数据模型

**Files:**
- Modify: `my_agent/config/settings.py`
- Modify: `my_agent/agent/subagent.py`
- Modify: `my_agent/session/models.py`
- Test: `my_agent/tests/test_subagent.py`

**Interfaces:**
- `Settings.max_concurrent_subagents: int`，默认 `3`，环境别名 `MY_AGENT_MAX_CONCURRENT_SUBAGENTS`，范围 `1..8`。
- 新增不可变事件/结果数据类：`SubagentTaskResult(task_index, task, status, summary, error)`、`SubagentProgressEvent(batch_id, result, completed_count, total)`、`SubagentBatchEvent(batch_id, session_id, task_results)`。
- `ChatMessage.metadata: dict[str, Any] | None` 可选，旧会话缺失该字段时按 `None` 恢复；内部批次记录用 `metadata={"kind": "subagent_batch", "batch_id": ...}` 标识。
- `SubagentManager.start_batch(tasks: list[str], session_id: str) -> str` 立即返回批次 ID；`SubagentManager.poll_events() -> list[object]` 非阻塞返回事件；`SubagentManager.cancel_all() -> None` 取消未完成任务。

- [ ] **Step 1: 写失败测试**：增加配置默认/边界测试；增加 `start_batch` 立即返回、任务并行且最多 3 个 worker、单项结果事件和整批单事件测试。
- [ ] **Step 2: 运行测试确认失败**：`pytest my_agent/tests/test_subagent.py -q`，应因字段、事件类型和批次方法不存在而失败。
- [ ] **Step 3: 实现最小批次协调器**：在现有 `SubagentManager.run` 基础上抽出单任务执行函数；以 `ThreadPoolExecutor(max_workers=...)` 提交任务；future 完成回调只写入事件队列，并在计数达到总数时写入一条批次事件；保留结果长度限制和异常转摘要。
- [ ] **Step 4: 运行测试确认通过**：`pytest my_agent/tests/test_subagent.py -q`。
- [ ] **Step 5: 提交**：`git add my_agent/config/settings.py my_agent/agent/subagent.py my_agent/tests/test_subagent.py; git commit -m "feat: 增加并行子Agent批次协调器"`。

### Task 2: 批量委派工具与应用组装

**Files:**
- Create: `my_agent/tools/spawn_subagents_tool.py`
- Modify: `my_agent/app.py`
- Modify: `my_agent/tests/test_app.py`
- Modify: `my_agent/tests/test_subagent.py`

**Interfaces:**
- `SpawnSubagentsTool(manager, session_id_provider)` 暴露工具名 `spawn_subagents`，参数 `{tasks: string[]}`；成功返回批次 ID、任务数和“已分派”摘要，拒绝空列表、重复任务及超过配置上限的列表。
- `SubagentManager.start_batch` 的 `session_id` 由当前 REPL 会话注入，不在工具内部读取全局状态。

- [ ] **Step 1: 写失败测试**：验证 schema、参数校验、批次启动和 `build_app()` 注册工具；验证子 Agent 的工具注册表不含 `spawn_subagents`。
- [ ] **Step 2: 运行测试确认失败**：`pytest my_agent/tests/test_app.py my_agent/tests/test_subagent.py -q`。
- [ ] **Step 3: 实现工具和组装**：按现有 `SpawnSubagentTool` 风格实现 schema/run；在 `build_app` 中用配置创建 manager 并注册新工具，同时保留兼容的单任务工具，避免破坏已有调用。
- [ ] **Step 4: 运行测试确认通过**：同上 pytest 命令。
- [ ] **Step 5: 提交**：`git add my_agent/tools/spawn_subagents_tool.py my_agent/app.py my_agent/tests/test_app.py my_agent/tests/test_subagent.py; git commit -m "feat: 添加批量子Agent委派工具"`。

### Task 3: REPL 事件消费、会话持久化与汇总轮

**Files:**
- Modify: `my_agent/app.py`
- Modify: `my_agent/agent/loop.py`
- Modify: `my_agent/session/manager.py`
- Modify: `my_agent/session/models.py`
- Modify: `my_agent/tests/test_app.py`
- Create: `my_agent/tests/test_parallel_repl.py`

**Interfaces:**
- `AgentLoop.handle_subagent_batch(session_id: str, event: SubagentBatchEvent) -> str` 将批次结果写成内部会话记录，并调用一次现有上下文/runner 生成汇总回复。
- `AppState` 增加 `subagent_manager` 字段；REPL 每次读取输入前和每轮前台请求完成后调用 `_drain_subagent_events`。

- [ ] **Step 1: 写失败测试**：验证前台忙碌时批次事件留在待处理队列；空闲后逐项打印完成提示；整批只触发一次 `handle_subagent_batch`；批次记录和最终回复写入 session；退出时调用 `cancel_all`。
- [ ] **Step 2: 运行测试确认失败**：`pytest my_agent/tests/test_parallel_repl.py -q`。
- [ ] **Step 3: 实现会话内部记录**：扩展 `ChatMessage` 的可选 metadata 序列化和 `SessionManager` 的追加逻辑，保持旧 JSON 格式兼容；在 `AgentLoop` 中构造受限摘要上下文，调用一次 runner，并保存内部记录及 assistant 汇总消息。
- [ ] **Step 4: 实现 REPL 消费逻辑**：在同步 `handle_user_message` 调用期间不消费整批事件；调用返回后先输出已到达的单项完成提示，再处理已完成批次并打印汇总回复；批次事件在前台轮期间只留在队列中；在 `finally` 中取消并等待后台任务。
- [ ] **Step 5: 运行测试确认通过**：`pytest my_agent/tests/test_parallel_repl.py my_agent/tests/test_app.py my_agent/tests/test_subagent.py -q`。
- [ ] **Step 6: 提交**：`git add my_agent/app.py my_agent/agent/loop.py my_agent/session/manager.py my_agent/tests/test_parallel_repl.py my_agent/tests/test_app.py; git commit -m "feat: 在REPL中汇总并行子Agent结果"`。

### Task 4: 回归验证与文档检查

**Files:**
- Modify: `my_agent/tests/test_runner.py` only if tool-call compatibility coverage is needed.

- [ ] **Step 1: 运行完整相关测试**：`pytest my_agent/tests -q`。
- [ ] **Step 2: 运行静态检查**：`ruff check my_agent/`。
- [ ] **Step 3: 手动验证 REPL**：启动、空输入、普通问答不触发委派、`quit`/`exit`、`Ctrl+C`、EOF，以及一个包含两个独立任务的批次；确认单项完成提示、整批一次汇总和会话可续用。
- [ ] **Step 4: 检查变更范围**：`git status --short`，确认只包含 `my_agent/` 实现/测试及已批准文档，未修改 `nanobot/`、`bridge/` 或敏感存储。
