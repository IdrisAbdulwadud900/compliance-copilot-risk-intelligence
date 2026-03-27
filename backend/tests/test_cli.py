import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

from app.cli import main
from app.migrations import available_migration_versions


class _HealthHandler(BaseHTTPRequestHandler):
    response_payload = {"status": "ok", "service": "test-service"}

    def do_GET(self):  # noqa: N802
        body = json.dumps(type(self).response_payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003
        return


def _start_health_server(payload: dict[str, str]) -> tuple[HTTPServer, threading.Thread]:
    handler = type("DynamicHealthHandler", (_HealthHandler,), {"response_payload": payload})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_cli_migrate_applies_all_versions(tmp_path, capsys):
    db_path = str(tmp_path / "cli_migrate.db")

    exit_code = main(["migrate", "--db-path", db_path])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "result=migrated" in captured.out
    assert f"applied={','.join(str(version) for version in available_migration_versions())}" in captured.out
    assert "pending=none" in captured.out


def test_cli_status_reports_pending_then_applied(tmp_path, capsys):
    db_path = str(tmp_path / "cli_status.db")

    before_code = main(["status", "--db-path", db_path])
    before_output = capsys.readouterr().out
    assert before_code == 0
    assert "applied=none" in before_output
    assert f"pending={','.join(str(version) for version in available_migration_versions())}" in before_output

    migrate_code = main(["migrate", "--db-path", db_path])
    assert migrate_code == 0
    _ = capsys.readouterr()

    after_code = main(["status", "--db-path", db_path])
    after_output = capsys.readouterr().out
    assert after_code == 0
    assert f"applied={','.join(str(version) for version in available_migration_versions())}" in after_output
    assert "pending=none" in after_output


def test_cli_missing_env_file_returns_error(tmp_path, capsys):
    db_path = str(tmp_path / "cli_env_error.db")

    exit_code = main(["--env-file", str(tmp_path / "missing.env"), "migrate", "--db-path", db_path])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error=Environment file not found" in captured.out


def test_cli_health_reports_ok_response(capsys):
    server, thread = _start_health_server({"status": "ok", "service": "test-service"})
    try:
        url = f"http://127.0.0.1:{server.server_port}/health"
        exit_code = main(["health", "--url", url, "--timeout-seconds", "1", "--interval-seconds", "0.1"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert f"health_url={url}" in captured.out
        assert "health_status=ok" in captured.out
        assert "service=test-service" in captured.out
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_cli_health_returns_error_for_unreachable_service(capsys):
    exit_code = main([
        "health",
        "--url",
        "http://127.0.0.1:9/health",
        "--timeout-seconds",
        "0.2",
        "--interval-seconds",
        "0.05",
    ])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error=Health check failed" in captured.out


def test_cli_preflight_runs_migrate_and_health(tmp_path, capsys):
    db_path = str(tmp_path / "cli_preflight.db")
    server, thread = _start_health_server({"status": "ok", "service": "preflight-service"})
    try:
        url = f"http://127.0.0.1:{server.server_port}/health"
        exit_code = main([
            "preflight",
            "--db-path",
            db_path,
            "--url",
            url,
            "--timeout-seconds",
            "1",
            "--interval-seconds",
            "0.1",
        ])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "pending=none" in captured.out
        assert "health_status=ok" in captured.out
        assert "result=preflight_ok" in captured.out
    finally:
        server.shutdown()
        thread.join(timeout=2)