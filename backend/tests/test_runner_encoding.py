"""Локальный фолбэк раннера: кириллица в выводе не должна превращаться в кракозябры."""

from unittest.mock import patch

from game import runner


def test_fallback_decodes_cyrillic_output():
    res = runner._execute_subprocess_fallback('print("Привет, мир")', timeout=10)
    assert "Привет, мир" in res["output"]


def test_fallback_forces_utf8_in_child():
    # флаг -I игнорирует PYTHONUTF8/PYTHONIOENCODING, поэтому UTF-8 включаем через -X utf8
    with patch.object(runner.subprocess, "run") as run:
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        run.return_value.returncode = 0
        runner._execute_subprocess_fallback("print(1)", timeout=1)
    args = run.call_args[0][0]
    assert args[args.index("-X") + 1] == "utf8"
