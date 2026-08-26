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

这些工具会根据模型输出执行操作，存在修改文件、运行命令和访问网络的风险。不要把含有密钥、个人数据或重要生产资源的目录作为工作目录。

### 命令沙箱

在 Windows 上，`my_agent` 的 `exec` 和命令会话工具通过 WSL2（Windows 的 Linux 子系统）调用 Bubblewrap（Linux 进程隔离工具）执行。沙箱仅将当前工作目录映射为 `/workspace`，Linux 运行时目录只读挂载，网络默认关闭；无法使用后端时会拒绝执行，不会退回为普通 Windows 子进程。

命令运行在 Ubuntu 环境，因此应使用 Linux 命令，例如 `ls`、`sh` 和 `python3`，不要使用 `dir`、`cmd.exe` 或 Windows 路径。

首次使用前需要安装 Ubuntu WSL2，并在其中安装 Bubblewrap：

```powershell
wsl --install Ubuntu
```

```bash
sudo apt-get update
sudo apt-get install bubblewrap
```

可通过以下变量选择 WSL 发行版和其中的普通用户：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `MY_AGENT_SANDBOX_WSL_DISTRO` | 执行 Bubblewrap 的 WSL 发行版名称 | `Ubuntu` |
| `MY_AGENT_SANDBOX_WSL_USER` | WSL 内执行沙箱命令的普通用户名 | 当前 Windows 用户名 |

不要将 WSL 用户配置为 `root`。当前实现只隔离命令执行；文件工具和网页工具仍应按照工作区和网络安全规则继续收紧。

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
