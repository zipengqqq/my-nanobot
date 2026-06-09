from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.provider import OpenAICompatProvider
from my_agent.agent.runner import AgentRunner
from my_agent.config import Settings
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry


@dataclass(slots=True)
class AppState:
    settings: Settings
    loop: AgentLoop


def build_app(env_file: Path | str | None = None) -> AppState:
    """构建应用运行时依赖，并返回 CLI 需要的最小状态对象。

    这个函数在当前项目里相当于“装配层”：

    - 先读取 `.env` 配置
    - 再创建 session、tools、provider、context、runner
    - 最后把这些对象注入 `AgentLoop`

    这样做的目的，是把“对象如何创建”集中放在入口层，
    避免把依赖创建逻辑散落到 `AgentLoop`、`AgentRunner` 等核心类里。

    参数:
        env_file: 可选的 `.env` 文件路径。传入后优先读取该文件，
            便于测试或你在本地切换不同配置。

    返回:
        AppState: 包含 `settings` 和 `loop` 的运行时对象。
            CLI 启动后，真正处理用户输入的是 `loop`，
            而 `settings` 则提供 session_id、history_limit 等配置。
    """

    # 先把配置读出来，后面的所有组件都依赖这里的参数。
    settings = Settings.from_env_file(env_file)

    # SessionManager 先用内存保存历史；后面 Phase 5 再换成落盘实现。
    session_manager = SessionManager(history_limit=settings.history_limit)

    # Phase 3 开始接入最小默认工具集，但注册和执行仍留在 ToolRegistry 这一层。
    tool_registry = ToolRegistry.with_defaults()

    # Provider 负责真正调用大模型接口；当前阶段只做单轮文本对话。
    provider = OpenAICompatProvider(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )

    # ContextBuilder 负责把 system prompt、history、user message 组装成 messages。
    context_builder = ContextBuilder()

    # AgentRunner 只关心“拿到 messages 以后如何调 provider”。
    runner = AgentRunner(provider=provider, tool_registry=tool_registry)

    # AgentLoop 是总编排层，负责把 session、context、runner 串起来。
    loop = AgentLoop(
        session_manager=session_manager,
        context_builder=context_builder,
        runner=runner,
    )
    return AppState(settings=settings, loop=loop)


def run_repl(env_file: Path | str | None = None) -> None:
    app_state = build_app(env_file=env_file)
    print("my_agent Phase 1 CLI 已启动，输入 quit 或 exit 退出。")

    while True:
        try:
            user_text = input("你> ").strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\n已退出")
            break

        if not user_text:
            continue
        if user_text.lower() in {"quit", "exit"}:
            break

        reply = app_state.loop.handle_user_message(
            session_id=app_state.settings.session_id,
            user_text=user_text,
        )
        print(f"助手> {reply}")


def main() -> None:
    run_repl()


if __name__ == "__main__":
    main()
