# Nanobot 架构地图

## 目标

这份文档不是复述整个 `nanobot` 仓库，而是抽取出“我们自己实现一个最小 CLI agent 时，必须理解并保留的核心架构”。

后续所有学习和开发都以这份文档为准。遇到新需求时，先判断它属于哪一层，再决定是否进入最小实现。

## 一句话模型

`nanobot` 的主链路可以压缩为：

`InboundMessage -> AgentLoop -> ContextBuilder -> AgentRunner -> ToolRegistry -> Session/Memory -> OutboundMessage`

真正的核心只有两层：

- `AgentLoop`：编排一轮消息处理
- `AgentRunner`：执行一轮 LLM + tools 推理循环

其它层都是给这两层提供输入、约束或持久化能力。

## 核心数据流

### 1. Channel / 入口层

职责：

- 接收外部消息
- 规范化成 `InboundMessage`
- 发布到 `MessageBus`

在 `nanobot` 里，这层很复杂，因为它支持很多渠道（Telegram、Slack、Feishu、WebSocket 等）。

在我们的最小实现里：

- 暂时只保留 CLI 入口
- 不做 `MessageBus`
- 直接构造一个最小的“输入消息对象”传给 `AgentLoop`

也就是说，我们会先跳过“多渠道适配”，保留“统一消息对象”这个思想。

### 2. AgentLoop：一轮 turn 的总编排

对应文件：

- [nanobot/agent/loop.py](/Users/penn/work/nanobot/nanobot/agent/loop.py)

职责：

- 读取 session 历史
- 恢复未完成 turn
- 构建本轮初始消息
- 调用 `AgentRunner`
- 保存本轮新消息
- 产出最终响应

这是“产品层编排器”，它不关心具体 provider 如何调，也不直接处理具体工具逻辑。

对最小实现最关键的认识：

- `AgentLoop` 负责“一轮消息处理”
- `AgentRunner` 负责“一轮推理循环”
- 两者不要混在一起

### 3. ContextBuilder：把 prompt 拼出来

对应文件：

- [nanobot/agent/context.py](/Users/penn/work/nanobot/nanobot/agent/context.py)

职责：

- 生成 system prompt
- 拼接历史消息
- 拼接当前用户消息
- 追加 runtime metadata

它是“上下文组装器”，不是“推理器”。

对最小实现要保留的点：

- system prompt 单独生成
- history 和 current message 明确分开
- 最终输出标准 `messages: list[dict]`

第一版不保留的点：

- skills
- MCP runtime lines
- 多模态图片块
- 复杂 runtime context 注入

### 4. AgentRunner：LLM + tools 的循环引擎

对应文件：

- [nanobot/agent/runner.py](/Users/penn/work/nanobot/nanobot/agent/runner.py)

职责：

- 向 provider 发起一次模型请求
- 识别模型是否要求调用工具
- 执行工具
- 把工具结果回填到消息列表
- 再次请求模型
- 直到得到最终回答或达到上限

这是整个 agent 的“心脏”。

要点：

- 它不负责 session 落盘
- 它不负责入口路由
- 它只负责本次推理循环

这也是我们自己实现 agent 时最先要做对的一层。

### 5. ToolRegistry：工具暴露面

对应文件：

- [nanobot/agent/tools/registry.py](/Users/penn/work/nanobot/nanobot/agent/tools/registry.py)

职责：

- 注册工具
- 输出工具 schema 给模型
- 校验工具参数
- 分发工具执行

这里要学到的不是“工具有多少种”，而是“模型看到的是 schema，运行时看到的是 registry”。

我们的最小实现会保留：

- `Tool` 抽象
- `ToolRegistry`
- 3 个工具：`read_file`、`list_dir`、`exec`

先不保留：

- MCP
- cron
- subagent
- image generation

### 6. SessionManager：会话历史

对应文件：

- [nanobot/session/manager.py](/Users/penn/work/nanobot/nanobot/session/manager.py)

职责：

- 按 session 保存消息
- 读取历史
- 控制 replay 窗口
- 保证历史回放合法

这里最重要的不是“存 JSONL”这个细节，而是两个不变量：

- 给模型的历史必须合法，不能从错误的 tool 边界开始
- 持久化历史不能污染模型，让模型学会复述内部元数据

我们的最小实现只保留：

- 单 session
- JSON 持久化
- 最近 N 轮历史

先不保留：

- unified session
- runtime checkpoint
- WebUI 标题、预览等 metadata

### 7. Memory / Consolidator：长期记忆和归档

对应文件：

- [nanobot/agent/memory.py](/Users/penn/work/nanobot/nanobot/agent/memory.py)

职责：

- 长期记忆文件
- 历史归档
- 超长上下文压缩

这层对完整 `nanobot` 很重要，但对第一阶段的学习不是必须。

我们的策略：

- 第一阶段不做长期记忆
- 只做短期 session history
- 第二阶段再引入“历史裁剪”
- 第三阶段再考虑“摘要归档”

## 最小 CLI 同构版本的保留层

第一阶段必须保留的层：

- `AgentLoop`
- `ContextBuilder`
- `AgentRunner`
- `ToolRegistry`
- `SessionManager`
- `ProviderAdapter`

第一阶段明确删除的层：

- `MessageBus`
- `channels/*`
- `WebUI`
- `MCP`
- `cron`
- `subagent`
- `goal_state`
- `auto_compact`
- `skills`

删除它们不是因为不重要，而是因为它们属于“边缘扩展”或“二阶段复杂度”。

## 我们自己的最小项目，建议同构目录

```text
mini_agent/
  app.py
  agent/
    loop.py
    runner.py
    context.py
    provider.py
  tools/
    base.py
    registry.py
    filesystem.py
    shell.py
  session/
    manager.py
    models.py
  storage/
    sessions/
```

这样做的理由：

- 名字和 `nanobot` 对齐，后续对照源码更自然
- 但目录数量控制在最小，不让结构先压死人

## 架构不变量

后续开发必须守住下面这些边界：

1. `AgentLoop` 不直接写 provider 细节。
2. `AgentRunner` 不直接读写 session 文件。
3. `ContextBuilder` 只负责拼上下文，不负责做推理决策。
4. `ToolRegistry` 只负责工具注册、校验、分发。
5. 入口层可以替换，但 `AgentLoop -> AgentRunner` 主链路尽量不变。

## 开发时的对照方式

每做一层，都问 3 个问题：

1. 这一层在 `nanobot` 对应哪个文件？
2. 这一层解决的核心问题是什么？
3. 我们现在删掉了哪些复杂度，为什么删？

如果说不清这 3 个问题，说明还不应该开始写那一层代码。

## 当前结论

我们接下来不会“从零自由发挥”做一个 agent，而是：

- 以 `nanobot` 为参考架构
- 用最小 CLI 版本复现其核心分层
- 每一轮都按这份架构地图校正方向

这能最大限度降低多轮对话带来的架构漂移。
