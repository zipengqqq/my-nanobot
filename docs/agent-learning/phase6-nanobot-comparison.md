# Phase 6：`my_agent` 与 `nanobot` 逐层对照

## 目的

这一阶段不再给 `my_agent` 增加新功能，而是回答 3 个问题：

1. 我们自己实现的每一层，在 `nanobot` 里对应什么位置？
2. 这一层解决的本质问题是什么？
3. `nanobot` 里的哪些复杂度，我们现在是有意识地删掉了？

如果这 3 个问题说不清，前 5 个 phase 写出来的代码就还只是“能跑”，不是“理解了”。

## 1. 入口与装配层

### `my_agent`

- `my_agent/app.py`

### `nanobot`

- `nanobot/cli/commands.py`
- `nanobot/nanobot.py`
- `nanobot/agent/loop.py` 的初始化装配部分

### 保留的本质

- 入口层负责读取配置并装配依赖。
- 核心对象之间通过注入连接，而不是在运行时互相偷偷创建。

### 当前删掉的复杂度

- 多渠道启动方式
- gateway / API server / WebUI
- provider snapshot、preset、runtime event bus

### 当前结论

`build_app()` 的价值，不是“写一个方便启动的函数”，而是把“依赖如何创建”压在最外层。  
这和 `nanobot` 的方向一致，只是我们保留了最小版本。

## 2. AgentLoop：一轮 turn 的编排器

### `my_agent`

- `my_agent/agent/loop.py`

### `nanobot`

- `nanobot/agent/loop.py`

### 保留的本质

- 读取 session 历史
- 构建本轮 messages
- 调用 runner
- 把本轮新增消息写回 session
- 返回最终文本

### 当前删掉的复杂度

- `MessageBus` 与 `InboundMessage` / `OutboundMessage`
- command router
- hooks / progress callback
- subagent、goal state、cron、runtime 注入
- session compaction / restore / continuation

### 当前结论

`my_agent.AgentLoop` 已经保住了最关键的边界：  
它知道“一轮对话如何串起来”，但不知道 provider 的 HTTP 细节，也不知道具体工具怎么执行。

## 3. ContextBuilder：上下文组装层

### `my_agent`

- `my_agent/agent/context.py`

### `nanobot`

- `nanobot/agent/context.py`

### 保留的本质

- system prompt 单独生成
- history 与当前 user message 明确拼接
- 输出标准 `messages` 列表给 provider

### 当前删掉的复杂度

- bootstrap files（如 `AGENTS.md`、`SOUL.md`）
- memory / skills / recent history
- runtime metadata lines
- 多模态内容块
- session summary / archived context

### 当前结论

这一层的本质不是“prompt engineering”，而是“把不同来源的上下文放在正确位置”。  
`my_agent` 现在只保留了最小 system + history + current user，但职责边界已经和 `nanobot` 对齐。

## 4. AgentRunner：LLM + tools 的循环引擎

### `my_agent`

- `my_agent/agent/runner.py`

### `nanobot`

- `nanobot/agent/runner.py`

### 保留的本质

- 发起模型请求
- 识别 tool call
- 执行工具并回填消息
- 继续迭代直到拿到最终文本
- 用 `max_iterations` 约束循环收敛

### 当前删掉的复杂度

- async hook 生命周期
- 并发工具执行
- streaming / progress event
- length recovery / retry / provider error recovery
- injection / sustained goal continuation
- tool result 持久化卸载与恢复

### 当前结论

这一层是 `my_agent` 和 `nanobot` 最同构的一层。  
差别主要不在“有没有循环”，而在 `nanobot` 为产品化运行补了大量异常恢复和运行时控制。

## 5. ToolRegistry：模型可见面与运行时分发面

### `my_agent`

- `my_agent/tools/registry.py`
- `my_agent/tools/base.py`

### `nanobot`

- `nanobot/agent/tools/registry.py`
- `nanobot/agent/tools/base.py`

### 保留的本质

- 工具注册
- 输出 schema 给模型
- 按名称分发执行

### 当前删掉的复杂度

- 参数类型转换与校验
- 稳定排序与 schema cache
- async tool execute
- MCP 工具命名空间
- workspace 安全边界与 richer error hint

### 当前结论

这一层最重要的学习点已经保留下来：  
模型看到的是 schema，运行时真正依赖的是 registry。  
`nanobot` 复杂的地方，不在“有更多工具”，而在“工具生态更大，所以注册、排序、校验、安全边界都必须更严”。

## 6. SessionManager：历史持久化与合法回放

### `my_agent`

- `my_agent/session/manager.py`
- `my_agent/session/models.py`

### `nanobot`

- `nanobot/session/manager.py`

### 保留的本质

- 历史与运行时分层
- 重启后可恢复 session
- 回放给模型的是合法消息序列
- 历史裁剪不能把一个 user turn 截断在半路

### 当前删掉的复杂度

- metadata、标题、预览
- token 预算裁剪
- consolidated archive
- timestamp 注入
- 图片 / CLI app / MCP 附件 breadcrumb
- unified session 与 WebUI 相关字段

### 当前结论

`nanobot` 在这层的复杂度，很多都不是“多余设计”，而是产品规模下必须处理的历史合法性问题。  
`my_agent` 现在只保留了最小 JSON session，但已经学到了最关键的不变量：  
持久化层必须保存足够结构，才能在下一轮重新变成合法上下文。

## 7. ProviderAdapter：隔离外部模型接口

### `my_agent`

- `my_agent/agent/provider.py`

### `nanobot`

- `nanobot/providers/base.py`
- `nanobot/providers/*`

### 保留的本质

- 把模型接口调用封装在独立层
- 对上层暴露统一响应结构

### 当前删掉的复杂度

- 多 provider 适配
- reasoning / streaming / multimodal
- provider-specific response normalization
- model registry 与 discovery

### 当前结论

这层现在很薄，但方向是对的。  
只要 `AgentRunner` 依赖的是统一 `ProviderAdapter`，后续扩展 provider 时就不会污染主链路。

## 哪些复杂度属于“本质复杂度”

下面这些，即使继续做第二阶段，大概率也仍然要保留：

- `AgentLoop` 与 `AgentRunner` 分层
- `ContextBuilder` 单独负责拼上下文
- `ToolRegistry` 作为工具暴露与执行入口
- `SessionManager` 保证历史回放合法
- `ProviderAdapter` 屏蔽模型接口差异

这些不是 `nanobot`“写复杂了”，而是 agent 最小闭环本来就需要的骨架。

## 哪些复杂度属于“规模复杂度”

下面这些，是产品化后自然长出来的：

- 多渠道 / message bus
- hooks / runtime events / progress streaming
- memory / compaction / archived summary
- skills / bootstrap files / instruction loading
- MCP / subagent / cron / goal orchestration
- 更严格的工具参数校验与安全边界

这些复杂度并不是现在不重要，而是它们依赖前面那条最小主链路先足够稳。

## Phase 6 之后的结论

到这里，`my_agent` 的第一阶段已经完成了两件事：

1. 亲手做出一条最小但完整的 agent 主链路。
2. 能把这条主链路和 `nanobot` 的同构关系说清楚。

所以接下来如果继续扩展，重点不应该是“再随便加点功能”，而应该是先明确：  
下一次引入的复杂度，到底是在补本质层，还是在补产品规模层。
