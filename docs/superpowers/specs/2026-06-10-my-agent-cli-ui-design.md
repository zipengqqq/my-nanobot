# My Agent CLI UI 设计文档

## 目标

在不改变 `my_agent` 核心架构的前提下，把当前“纯 `input()` + `print()`”的 REPL 界面升级成更接近 Claude Code 风格的紧凑聊天壳。

这次改造的目标只有三点：

1. 提升终端中的信息层次和可读性。
2. 增加 assistant 回复的流式展示体验。
3. 让 agent 执行过程以“默认简洁、必要时展开”的方式暴露出来。

本次改造明确只作用于 CLI 展示层，不改 `AgentLoop -> AgentRunner -> SessionManager` 的主链路职责。

## 用户已确认的方向

- 布局方向：`A. 紧凑聊天壳`
- 过程信息策略：`3. 混合模式`
  - 平时只显示一行摘要
  - 进入工具调用或长执行时自动展开详细过程块
- 运行形态：`1. 普通命令行`
  - 保持当前 REPL 往下滚动的交互方式
  - 不做全屏 TUI
- 输出方式：需要流式显示 assistant 回复

## 范围

本次包含：

- 基于 `rich` 的终端渲染
- 顶部 header 区
- 用户 / assistant / system-like activity 的分块展示
- Markdown / Table 的终端渲染
- assistant 回复伪流式输出
- 过程摘要和详细过程块
- 最小测试补充

本次不包含：

- 修改 provider 协议为真实 streaming API
- 改造 `AgentLoop`、`AgentRunner` 的核心职责
- 全屏 TUI
- 鼠标交互、折叠面板、复杂快捷键
- 工具输出的完整审计视图

## 设计原则

### 1. UI 只属于入口层

终端壳层只能存在于 `my_agent/app.py` 及其新建的 CLI 辅助模块中。

以下层不应依赖 `rich`：

- `agent/`
- `session/`
- `tools/`

这样可以保证：

- CLI 渲染不会污染 agent 核心层
- 后续若改成别的前端，主链路不需要回退

### 2. 先做观感流式，不先做协议流式

当前 `OpenAICompatProvider` 仍然返回完整文本结果。本阶段不先改 provider 为原生流式接口，而是在 CLI 层对最终文本做逐步输出。

这样做的原因：

- 用户想要的是“界面体验先像起来”
- 当前学习项目的重点仍然是架构边界，不是 provider streaming 实现
- 伪流式足以满足本阶段的交互目标

后续若单独进入“provider streaming 能力”主题，可以再把这层从伪流式替换为真实 token stream。

### 3. 过程信息默认克制

默认状态下，用户看到的是简短过程摘要，例如：

- `Read 2 files`
- `Called read_file`
- `Used 1 tool in 2 steps`

只有在以下情形自动展开详细过程块：

- 本轮发生工具调用
- 本轮执行时间超过阈值
- 本轮出现异常

这样既保留 agent 过程感，也避免每轮输出都变成噪音。

## 技术方案

### 方案选择

候选方案有三种：

1. `rich` 轻改造
2. `rich + prompt_toolkit`
3. 全面 TUI 化

最终选择：`1. rich 轻改造`

理由：

- 仓库已具备 `rich` 依赖
- 能实现目标截图中的大部分观感
- 不需要引入更复杂的输入事件管理
- 与当前学习阶段的“只改壳层，不动主链路”目标一致

## 模块设计

建议新增一个轻量 CLI 包，例如：

```text
my_agent/
  cli/
    __init__.py
    renderer.py
    streaming.py
    activity.py
```

### 1. `CliRenderer`

职责：

- 渲染启动 header
- 渲染用户消息块
- 渲染 assistant 消息块
- 渲染过程摘要 / 详细过程块
- 渲染错误块和退出提示

建议提供的方法：

- `render_header(settings)`
- `render_user_message(text)`
- `render_activity_summary(summary)`
- `render_activity_detail(detail)`
- `render_assistant_markdown(text)`
- `render_error(text)`

说明：

- 这是一个纯展示对象
- 不负责 session、provider、tool 执行逻辑

### 2. `StreamingPrinter`

职责：

- 把最终回复文本按小粒度逐步写到终端
- 控制每步刷新的节奏
- 保证流式结束后终端换行完整

建议接口：

- `stream_text(text: str) -> None`

实现建议：

- 先按词或短片段流出，而不是逐字符
- 这样能减少终端抖动，也更自然

### 3. `ActivityReporter`

职责：

- 根据本轮执行结果推导“过程信息该怎么显示”
- 生成摘要文案
- 在满足条件时生成详细块内容

本阶段不追求完整的运行时遥测系统，只做最小启发式规则。

可用输入来源：

- `RunnerResult.new_messages`
- assistant/tool 消息数量
- 是否存在 tool 消息
- 本轮执行耗时
- 捕获到的异常

## 界面布局

### 1. 启动区

程序启动后先打印一次 header，包含：

- 应用名，例如 `my_agent v0.1`
- 当前模型
- 当前 session id
- `streaming on`
- 当前工作目录

这一块只在程序启动时打印，不在每轮重复输出。

### 2. 会话流

每轮对话按如下顺序向下滚动：

1. 用户消息块
2. 过程摘要
3. 若触发展开条件，则打印详细过程块
4. assistant 流式输出块

assistant 回复完成后，不再补打一份重复全文。

### 3. 过程块样式

过程块分两层：

- 摘要层：单行、低视觉权重
- 详细层：Panel 或 Table，列出工具名、文件数、耗时、错误摘要等

目标是做到“看一眼知道 agent 干了什么”，但不压过主回复内容。

## 数据流设计

本次改造后，CLI 主链路保持不变，只在入口层增加显示步骤：

`input -> render user block -> call AgentLoop -> derive activity -> stream assistant block`

注意：

- `AgentLoop.handle_user_message()` 仍然是主要业务入口
- 若需要展示更丰富的过程信息，可以在不破坏架构的前提下，让入口层读取 `RunnerResult` 可推导的信息
- 若当前接口不足以支撑过程显示，应优先增加最小只读结果结构，而不是把渲染逻辑塞回核心层

## 兼容性与约束

### 1. 与现有架构兼容

本设计不要求修改：

- `ContextBuilder` 消息组装职责
- `AgentRunner` 工具循环职责
- `SessionManager` 持久化职责

### 2. 与终端环境兼容

优先兼容普通 ANSI 终端，不假设：

- 全屏 alternate screen
- 鼠标支持
- 固定终端尺寸

### 3. 与测试环境兼容

渲染代码需要尽量可测试，不依赖真实用户输入。

建议通过：

- 注入 `Console(record=True)` 或等价对象
- 测试最终渲染文本片段

## 错误处理

需要处理三类错误：

### 1. provider / agent 调用异常

- CLI 捕获异常
- 用明显但不过度冗长的错误块打印
- 不让终端停在半截流式输出状态

### 2. 流式渲染中断

- `KeyboardInterrupt` 时优雅换行并退出
- 避免残留半行 prompt

### 3. Markdown 渲染退化

- 若某段内容不适合 Markdown 渲染，允许回退为普通文本输出
- 不让格式化失败影响主回复展示

## 测试设计

本次只补最小高价值测试，不做重型快照测试。

建议新增覆盖：

1. Header 渲染测试
   - 根据 `Settings` 输出模型、session、streaming 标记

2. Activity 分支测试
   - 无工具调用时只生成简洁摘要
   - 有工具调用时生成详细过程块

3. Streaming 输出测试
   - 流式输出完成后的文本与原文本一致

4. CLI 集成测试
   - REPL 入口在最小 fake loop 下能打印用户块和 assistant 块

## 验收标准

满足以下条件即可认为本次终端 UI 改造完成：

1. 启动后能看到清晰的 header 区。
2. 用户消息和 assistant 回复不再是裸 `print()`。
3. assistant 回复具备流式展示效果。
4. 过程信息默认简洁，但工具调用时会自动展开更详细块。
5. 改造后不需要修改 `AgentLoop`、`AgentRunner`、`SessionManager` 的核心职责。
6. 最小测试可以覆盖渲染分支和流式输出行为。

## 风险与后续

### 当前风险

- 伪流式不是模型原生 streaming，长回复时节奏感仍有限
- 若想展示非常细的过程数据，现有返回结构可能不够丰富
- `rich` 渲染在不同终端的视觉细节可能略有差异

### 后续可独立扩展的方向

这些不属于本次范围，但可作为后续独立主题：

- provider 原生 streaming
- 更丰富的 tool telemetry
- `prompt_toolkit` 输入增强
- 全屏 TUI

## 自审结论

已检查以下事项：

- 无 `TODO` / `TBD`
- 范围、技术方案、测试和验收标准一致
- 明确了“不改主链路，只改 CLI 壳层”的边界
- 本次工作仍可作为单独实现计划推进，不需要继续拆分子项目
