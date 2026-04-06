from __future__ import annotations

from types import SimpleNamespace

import amex_ai_agent.rca.bq_executor as bq_executor


class _FakePopen:
    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._polled = False

    def poll(self):
        if not self._polled:
            self._polled = True
            return None
        return self.returncode

    def communicate(self):
        return self._stdout, self._stderr


def test_run_bq_query_success(monkeypatch):
    monkeypatch.setattr(bq_executor.subprocess, "Popen", lambda *args, **kwargs: _FakePopen(0, '[{"x":1}]'))
    monkeypatch.setattr(bq_executor.time, "sleep", lambda _: None)

    result = bq_executor.run_bq_query("select 1", name="smoke")

    assert result.status == "success"
    assert result.row_count == 1


def test_run_bq_query_failure(monkeypatch):
    monkeypatch.setattr(bq_executor.subprocess, "Popen", lambda *args, **kwargs: _FakePopen(1, '', 'bad query'))
    monkeypatch.setattr(bq_executor.time, "sleep", lambda _: None)

    result = bq_executor.run_bq_query("select * from", name="broken")

    assert result.status == "error"
    assert "bad query" in result.error
