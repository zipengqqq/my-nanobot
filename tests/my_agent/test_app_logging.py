import logging
from pathlib import Path
from types import SimpleNamespace

from my_agent.app import AppState, run_repl
from my_agent.config import logger as app_logger


def test_run_repl_writes_logs_to_file(monkeypatch, tmp_path: Path) -> None:
    log_file = tmp_path / "my_nanobot.log"

    class FakeLoop:
        def handle_user_message(self, session_id: str, user_text: str) -> str:
            assert session_id == "lesson"
            assert user_text == "你好"
            return "世界"

    app_state = AppState(
        settings=SimpleNamespace(session_id="lesson"),
        loop=FakeLoop(),
    )
    inputs = iter(["你好", "exit"])
    test_logger = logging.getLogger("tests.my_agent.app_logging")
    test_logger.handlers.clear()
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    test_logger.addHandler(file_handler)
    test_logger.setLevel(logging.INFO)
    test_logger.propagate = False

    monkeypatch.setattr("my_agent.app.build_app", lambda env_file=None: app_state)
    monkeypatch.setattr("my_agent.app.logger", test_logger)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    run_repl()

    file_handler.flush()

    assert log_file.exists()
    log_text = log_file.read_text(encoding="utf-8")
    assert "CLI started" in log_text
    assert "user> 你好" in log_text
    assert "assistant> 世界" in log_text


def test_logger_singleton_is_exposed_from_config_module() -> None:
    assert isinstance(app_logger, logging.Logger)
