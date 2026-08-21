# my_agent

`my_agent` 是一个面向本地开发的轻量终端 REPL Agent。它通过 OpenAI 兼容的 Chat Completions 接口与模型交互，维护本地会话历史，并可按模型请求调用文件、命令和网页工具。

本项目从 `nanobot` 的代码与设计中学习实现方式，但当前只维护 `my_agent/` 中的终端 Agent，不包含 WebUI、桌面端、聊天渠道、Docker 部署或发布打包功能。

## 当前能力

- 在终端中进行多轮对话。
- 接入 OpenAI 及兼容 Chat Completions API 的模型服务。
- 将指定会话的最近对话保存为本地 JSON 文件。
- 支持文件读取、目录查看、文件搜索、文本搜索、写入和编辑。
- 支持执行本地命令，以及启动和管理长时间运行的命令会话。
- 支持网页搜索和网页内容抓取。

## 环境要求

- Python 3.11 或更高版本。
- 可访问的 OpenAI 兼容 API。
- 项目依赖已安装。开发环境可在仓库根目录执行：

```powershell
pip install -e .
```

## 配置

在 `my_agent/.env` 中创建配置文件。不要将此文件提交到版本控制。

```dotenv
OPENAI_BASE_URL=https://api.example.com/v1
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=your-model-name

MY_AGENT_SESSION_ID=local-dev
MY_AGENT_HISTORY_LIMIT=20
MY_AGENT_MAX_ITERATIONS=6
```

可选配置：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `OPENAI_BASE_URL` | OpenAI 兼容接口的基础地址 | 必填 |
| `OPENAI_API_KEY` | API 密钥 | 必填 |
| `OPENAI_MODEL` | 模型名称 | 必填 |
| `MY_AGENT_SESSION_ID` | 本次 REPL 使用的会话标识 | 必填 |
| `MY_AGENT_HISTORY_LIMIT` | 每个会话保留的最近用户轮次数 | 必填 |
| `MY_AGENT_MAX_ITERATIONS` | 单轮对话中模型与工具的最大交互次数 | `6` |
| `MY_AGENT_SESSION_STORAGE_DIR` | 会话 JSON 文件目录 | `my_agent/storage/sessions/` |

## 运行

从仓库根目录启动：

```powershell
python -m my_agent.app
```

启动后输入问题即可对话。输入 `quit` 或 `exit` 退出；按 `Ctrl+C` 或发送 `EOF` 也会结束 REPL。

会话默认保存在 `my_agent/storage/sessions/`。相同的 `MY_AGENT_SESSION_ID` 会在下次启动时加载对应历史记录。

## 工具与安全

模型可使用的工具在 `my_agent/tools/registry.py` 中注册，包括本地文件操作、Shell 命令、命令会话、网页搜索和网页抓取。

这些工具会根据模型输出执行操作，存在修改文件、运行命令和访问网络的风险。当前项目尚未提供完整的执行沙箱或网络隔离，因此只应在可信的本地工作目录、可信的模型服务和可信的提示词环境中运行。不要把含有密钥、个人数据或重要生产资源的目录作为工作目录。

`.env`、会话文件和日志都可能包含敏感信息，应保持在本机并排除在提交内容之外。

## 项目结构

```text
my_agent/
  app.py                 REPL 入口和运行时组装
  agent/
    context.py           构建系统提示词、会话历史与用户消息
    loop.py              编排单轮请求并写回会话
    provider.py          OpenAI 兼容模型适配层
    runner.py            模型与工具调用循环
  config/                从 .env 加载配置并初始化日志
  session/               会话模型和本地 JSON 持久化
  storage/sessions/      默认会话存储目录
  tools/                 工具定义、注册和执行实现
```

调用链：

```text
终端输入 -> AgentLoop -> ContextBuilder -> AgentRunner -> ToolRegistry -> SessionManager -> 终端输出
```

## 开发

后续功能默认只修改 `my_agent/`。上游 `nanobot/` 目录仅用于参考类似能力的实现、错误处理和安全边界；不要恢复或修改已删除的上游模块，除非需求明确要求。

修改后可执行：

```powershell
ruff check my_agent/
python -m compileall my_agent
```

详细的开发约定见 [AGENTS.md](./AGENTS.md)。
