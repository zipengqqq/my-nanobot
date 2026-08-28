from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from my_agent.agent.context import ContextBuilder
from my_agent.agent.loop import AgentLoop
from my_agent.agent.provider import OpenAICompatProvider
from my_agent.agent.runner import AgentRunner
from my_agent.agent.skills import BUILTIN_SKILLS_DIR, SkillsLoader
from my_agent.config import Settings, logger
from my_agent.repl.input import persist_images, prompt_with_images
from my_agent.sandbox import SandboxPolicy, SandboxRunner
from my_agent.sandbox.wsl import WslBubblewrapBackend
from my_agent.session.manager import SessionManager
from my_agent.tools.registry import ToolRegistry

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class AppState:
    settings: Settings
    loop: AgentLoop
    session_id: str


@dataclass(slots=True)
class ReplTraceRenderer:
    """把模型的工具调用实时输出为简洁的 REPL 执行轨迹。"""

    console: Console
    _skill_active: bool = False

    def start_turn(self) -> None:
        self._skill_active = False

    def on_tool_call(self, name: str, arguments: dict[str, object]) -> None:
        if name == "read_file" and self._is_skill_path(arguments.get("path")):
            path = Path(str(arguments["path"]))
            self.console.print(Text(f"[技能] 读取 {path.parent.name}"))
            self._skill_active = True
            return

        prefix = "  " if self._skill_active else ""
        self.console.print(Text(f"{prefix}[工具] 调用 {name}"))

    @staticmethod
    def _is_skill_path(path: object) -> bool:
        return Path(str(path)).name == "SKILL.md"

def render_markdown_reply(console: Console, reply: str) -> None:
    console.print(Markdown(reply))


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
            而 `settings` 则提供 history_limit 等配置。
    """

    # 先把配置读出来，后面的所有组件都依赖这里的参数。
    settings = Settings.from_env_file(env_file)

    # SessionManager 负责 session 持久化；当前按 session 文件落到本地目录。
    session_manager = SessionManager(
        history_limit=settings.history_limit,
        storage_dir=settings.session_storage_dir,
    )

    # 接入最小默认工具集，但注册和执行仍留在 ToolRegistry 这一层。
    workspace_root = PROJECT_ROOT
    sandbox_runner = SandboxRunner(
        policy=SandboxPolicy.required(workspace_root),
        backends=[
            WslBubblewrapBackend(
                distro=settings.sandbox_wsl_distro,
                user=settings.sandbox_wsl_user,
            )
        ],
    )
    tool_registry = ToolRegistry.with_defaults(
        root=workspace_root,
        sandbox_runner=sandbox_runner,
        extra_read_roots=[BUILTIN_SKILLS_DIR],
        image_api_key=settings.image_api_key,
        image_model=settings.image_model,
        image_draw_url=settings.image_draw_url,
        image_task_url_template=settings.image_task_url_template,
        image_timeout_seconds=settings.image_timeout_seconds,
        image_max_images_per_turn=settings.image_max_images_per_turn,
    )

    # Provider 负责真正调用大模型接口
    provider = OpenAICompatProvider(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )

    # ContextBuilder 负责把 system prompt、history、user message 组装成 messages。
    context_builder = ContextBuilder(skills=SkillsLoader(workspace=workspace_root))

    # AgentRunner 只关心“拿到 messages 以后如何调 provider”。
    runner = AgentRunner(
        provider=provider,
        tool_registry=tool_registry,
        max_iterations=settings.max_iterations, # 单轮 agent loop 的最大迭代次数
    )

    # AgentLoop 是总编排层，负责把 session、context、runner 串起来。
    loop = AgentLoop(
        session_manager=session_manager,
        context_builder=context_builder,
        runner=runner,
    )
    return AppState(
        settings=settings,
        loop=loop,
        session_id=f"session-{uuid.uuid4().hex}",
    )


def run_repl(env_file: Path | str | None = None) -> None:
    app_state = build_app(env_file=env_file)
    console = Console()
    trace_renderer = ReplTraceRenderer(console)
    runner = getattr(app_state.loop, "runner", None)
    if isinstance(runner, AgentRunner):
        runner.on_tool_call = trace_renderer.on_tool_call
    logger.info("CLI 已启动 session_id=%s", app_state.session_id)
    print("my_codex 已启动，输入quit或exit退出")

    while True:
        try:
            user_text, images = prompt_with_images("你> ")
        except EOFError:
            logger.info("CLI 因 EOF 退出")
            print()
            break
        except KeyboardInterrupt:
            logger.info("CLI 因键盘中断退出")
            print("\n已退出")
            break

        if not user_text:
            continue
        if user_text.lower() in {"quit", "exit"}:
            logger.info("CLI 因用户退出命令结束")
            break

        if images:
            try:
                images = persist_images(
                    images,
                    PROJECT_ROOT / "my_agent" / "storage" / "reference-images",
                )
            except OSError as exc:
                logger.warning("无法保存本轮粘贴图片: %s", exc)
                print("无法保存粘贴图片，本轮不能将其用作图像生成参考。")
                continue

        logger.info("用户输入: %s", user_text)
        trace_renderer.start_turn()
        request = {
            "session_id": app_state.session_id,
            "user_text": user_text,
        }
        if images:
            request["images"] = images
        reply = app_state.loop.handle_user_message(**request)
        logger.info("助手回复: %s", reply)
        console.print(Text("assistant> "), end="")
        render_markdown_reply(console, reply)


def main() -> None:
    run_repl()


if __name__ == "__main__":
    main()
