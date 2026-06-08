# 最小 CLI Agent 构建路线图

## 目标

做一个和 `nanobot` 核心分层同构、但规模最小的 CLI agent。

第一阶段目标不是功能多，而是把这条主链路亲手做对：

`user input -> AgentLoop -> ContextBuilder -> AgentRunner -> ToolRegistry -> SessionManager -> output`

## 范围控制

### 第一阶段做什么

- CLI 单用户入口
- OpenAI-compatible provider
- 多轮历史
- 基础工具调用
- 本地 session 持久化

### 第一阶段不做什么

- WebUI
- 多渠道
- MCP
- cron
- subagent
- 长期记忆
- 图片、多模态
- 复杂权限系统

## 分阶段计划

### Phase 0：定结构，不写复杂逻辑

目标：

- 创建最小目录结构
- 定义核心对象和职责
- 确认调用方向

产物：

- `agent/loop.py`
- `agent/runner.py`
- `agent/context.py`
- `agent/provider.py`
- `tools/base.py`
- `tools/registry.py`
- `session/manager.py`
- `app.py`

完成标准：

- 各模块能 import 成功
- 能从 `app.py` 启动 CLI shell

### Phase 1：单轮对话

目标：

- 输入一条消息
- 组出 system + user messages
- 调一次模型
- 打印回复

你会学到：

- provider 抽象为什么要单独一层
- messages 为什么必须统一格式
- `ContextBuilder` 和 `AgentRunner` 为什么不能混在一起

完成标准：

- 命令行输入一句话，模型能回复一句话

### Phase 2：多轮历史

目标：

- 维护当前 session 的历史消息
- 第二轮提问时能带上第一轮上下文

你会学到：

- session 历史和当前 turn 的边界
- 为什么历史管理不该塞进 `AgentRunner`

完成标准：

- 第二轮提问可以引用前一轮内容

### Phase 3：工具注册与执行

目标：

- 定义 `Tool` 抽象
- 定义 `ToolRegistry`
- 增加 3 个工具：`read_file`、`list_dir`、`exec`

你会学到：

- 模型看到的是 tool schema
- 运行时拿到的是 registry 分发
- 工具执行错误为什么必须标准化返回

完成标准：

- 模型可以调用至少一个工具，并继续生成最终答案

### Phase 4：真正的 agent loop

目标：

- 支持 “模型回复” 与 “模型要求调工具” 两种分支
- 支持多轮 tool-call 循环
- 设置最大迭代次数

你会学到：

- `AgentLoop` 和 `AgentRunner` 的职责边界
- 为什么要有 “max_iterations”
- 为什么最终对话历史里要同时保存 assistant/tool/user 消息

完成标准：

- 模型可连续多次调工具，最终输出答案

### Phase 5：session 持久化

目标：

- 把历史保存到本地文件
- 重启 CLI 后恢复之前的会话

你会学到：

- 运行时状态和持久化状态的边界
- 为什么 `nanobot` 要把 session 单独做成一层

完成标准：

- 退出程序后重新进入，历史仍可读取

### Phase 6：回看 nanobot

目标：

- 把我们做的最小 agent 和 `nanobot` 一一对照
- 识别哪些复杂度是产品规模带来的

你会学到：

- 哪些分层是“本质复杂度”
- 哪些分层是“规模复杂度”

完成标准：

- 能说清我们和 `nanobot` 在每一层的异同

## 开发原则

1. 每次只做一层，不跨层偷懒。
2. 每加一层都要能跑、能打断点、能解释。
3. 每一阶段结束时，先验证理解，再继续写代码。
4. 如果某个抽象解释不清，就先不要引入。

## 每阶段固定输出

每完成一个 phase，都要留下 3 种产物：

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

## 当前推荐起点

下一步从 `Phase 0` 开始，不碰复杂实现，只完成：

- 目录结构
- 核心类骨架
- CLI 入口

原因：

- 这一步风险最低
- 能尽快把“分层骨架”固定下来
- 后面每层都能在这个骨架上增量生长
