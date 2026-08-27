# `nanobot/` 目录导览

本文介绍上游 `nanobot/` 包中各目录的职责，方便在为当前轻量终端 Agent 开发功能时查找可借鉴的实现。

> `nanobot/` 在本仓库中是上游参考代码；默认开发目标是 `my_agent/`。不要因为本文列出了某项上游能力，就将它视为当前 `my_agent/` 已支持或需要恢复的功能。

## 总览

`nanobot` 是一个包含命令行、聊天渠道、WebUI、定时任务和多模型适配的完整 Agent 框架。其大致运行关系如下：

```text
CLI / 聊天渠道 / HTTP API
            ↓
       bus（消息传递）
            ↓
 agent（上下文、循环、工具调用）
      ↙        ↓        ↘
session    providers    agent/tools
            ↓
      config / security / utils
```

## 目录职责

| 路径 | 职责 | 主要内容 |
| --- | --- | --- |
| `nanobot/agent/` | Agent 核心编排 | 构建模型上下文、执行模型与工具调用循环、维护记忆、加载技能、管理子 Agent、处理生命周期钩子和上下文压缩。`loop.py` 是核心处理引擎，`runner.py` 负责可复用的模型/工具执行循环。 |
| `nanobot/agent/tools/` | Agent 工具体系 | 定义工具基类、参数 Schema、注册与发现机制，以及文件、Shell、搜索、网页、MCP、消息、图像生成、定时任务、子 Agent 等具体工具；也包含工作区路径检查、沙箱和运行时状态等工具共用边界。 |
| `nanobot/api/` | OpenAI 兼容 HTTP API | 将固定的 nanobot 会话暴露为 OpenAI 兼容接口；`server.py` 提供服务端实现。 |
| `nanobot/apps/` | 可配置 Agent 应用的公共协议 | 定义由设置界面管理的应用清单（manifest）和公共数据结构。 |
| `nanobot/apps/cli/` | CLI 应用适配层 | 维护 CLI-Anything 类应用的目录、安装状态和受控执行，并向 Agent 循环与设置界面提供共用辅助函数。 |
| `nanobot/bus/` | 异步消息总线 | 定义入站/出站事件、异步队列、运行时事件和进度回调，使聊天渠道与 Agent 核心解耦。 |
| `nanobot/channels/` | 聊天平台接入 | 提供渠道抽象、渠道管理器、自动注册机制，以及 Telegram、Discord、Slack、飞书、企业微信、WhatsApp、QQ、邮件、WebSocket 等平台实现。 |
| `nanobot/cli/` | 命令行产品入口 | 定义 Typer 命令、交互式初始化向导、模型信息辅助逻辑与流式终端输出渲染；`nanobot/__main__.py` 通过它支持 `python -m nanobot`。 |
| `nanobot/command/` | 斜杠命令处理 | 提供轻量命令路由表，并注册内置命令处理器。 |
| `nanobot/config/` | 配置加载与路径管理 | 使用 Pydantic 定义配置 Schema，加载配置文件，并按活动配置上下文推导运行时路径。 |
| `nanobot/cron/` | 定时任务服务 | 定义 Cron 任务和调度类型，并负责定时触发 Agent 任务。 |
| `nanobot/pairing/` | 私信配对与发件人审批 | 保存和查询可与机器人私信交互的已批准发件人，供渠道接入层实施访问控制。 |
| `nanobot/providers/` | 大模型服务商抽象 | 定义统一 Provider 接口与工厂，适配 OpenAI 兼容接口、Anthropic、Azure OpenAI、AWS Bedrock、GitHub Copilot 等；还提供故障转移、语音转写与图像生成辅助能力。 |
| `nanobot/providers/openai_responses/` | OpenAI Responses API 共用适配 | 将 Chat Completions 风格的消息和工具转换为 Responses API 格式，并解析流式或 SDK 返回结果，供 Codex 和 Azure Provider 复用。 |
| `nanobot/security/` | 安全边界工具 | 提供网络地址校验与 SSRF 防护，以及工作区访问范围、路径边界和沙箱能力的公共判断。 |
| `nanobot/session/` | 会话和轮次状态 | 读取、保存与管理对话历史；维护持续目标状态，并为 WebUI 会话和续接轮次提供辅助逻辑。 |
| `nanobot/skills/` | 内置技能包 | 存放可被 Agent 加载的 `SKILL.md` 能力说明及其附属资源。各子目录按能力划分，见下表。 |
| `nanobot/templates/` | 提示词模板 | 存放 Jinja2 模板，供 `utils/prompt_templates.py` 组织 Agent 系统提示词和记忆模板。 |
| `nanobot/templates/agent/` | Agent 提示词模板 | 存放 Agent 角色、工具和运行行为相关的模板片段。 |
| `nanobot/templates/agent/_snippets/` | Agent 模板片段 | 存放可由 Agent 模板复用的小片段，避免重复维护提示词文本。 |
| `nanobot/templates/memory/` | 记忆模板 | 存放记忆整理、写入或读取时使用的提示词模板。 |
| `nanobot/utils/` | 通用辅助模块 | 提供日志桥接、路径和文档处理、媒体解码、产物存储、进度事件、提示词渲染、Git 记忆存储、运行时辅助等跨模块能力。 |
| `nanobot/web/` | 内嵌 Web 前端资源 | 保存随 Python 包分发的 WebUI 静态资源。 |
| `nanobot/webui/` | WebUI 后端服务 | 提供 WebSocket/HTTP 网关、设置 API、媒体与文件预览、会话转录、工作区和侧边栏状态、Token 用量等 WebUI 专用后端逻辑。 |

## 内置技能目录

`nanobot/skills/` 下的目录不是 Python 业务模块，而是供 Agent 按需加载的能力说明与资源：

| 路径 | 用途 |
| --- | --- |
| `nanobot/skills/clawhub/` | 与 ClawHub 技能生态或目录相关的操作说明。 |
| `nanobot/skills/cron/` | 创建和管理定时任务的操作说明。 |
| `nanobot/skills/github/` | GitHub 相关工作流的操作说明。 |
| `nanobot/skills/image-generation/` | 图像生成能力的使用说明。 |
| `nanobot/skills/long-goal/` | 长期目标与持续任务的操作说明。 |
| `nanobot/skills/memory/` | Agent 记忆管理的操作说明。 |
| `nanobot/skills/my/` | 项目自定义技能及其参考材料。 |
| `nanobot/skills/my/references/` | `my` 技能所引用的补充资料。 |
| `nanobot/skills/skill-creator/` | 创建或维护技能包的说明和辅助脚本。 |
| `nanobot/skills/skill-creator/scripts/` | 初始化、打包和快速校验技能包的脚本。 |
| `nanobot/skills/summarize/` | 内容摘要相关的操作说明。 |
| `nanobot/skills/tmux/` | 使用 tmux 管理终端任务的说明与工具资源。 |
| `nanobot/skills/tmux/scripts/` | tmux 技能使用的辅助脚本。 |
| `nanobot/skills/update-setup/` | 更新安装或运行环境的操作说明。 |
| `nanobot/skills/weather/` | 天气查询能力的操作说明。 |

## 如何参考上游实现

若目标是扩展当前 `my_agent/` 的终端 REPL，通常按以下顺序查阅上游代码即可：

1. `nanobot/agent/`：理解上下文构建、单轮编排和模型工具循环的职责划分。
2. `nanobot/agent/tools/` 与 `nanobot/security/`：参考工具注册、执行限制和安全边界。
3. `nanobot/session/`：参考会话持久化与历史读取的做法。
4. `nanobot/providers/`：参考不同模型服务商的协议隔离方式。

`channels/`、`webui/`、`api/`、`cron/` 等目录属于完整上游产品的扩展能力。除非需求明确涉及它们，否则不应将其迁入或恢复到 `my_agent/`。
