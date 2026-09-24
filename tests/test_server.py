"""
Comprehensive tests for the Yieldix Web Cockpit & Telemetry Server.
Runs against real listening HTTP socket on localhost without mocks.
"""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from yieldix.server.app import create_server


@pytest.fixture(scope="module")
def live_server():
    """Starts the real HTTP server on an ephemeral port in a daemon thread."""
    port = 8999
    server = create_server(host="127.0.0.1", port=port)
    thread = threading.Thread(target=server.start, kwargs={"blocking": True}, daemon=True)
    thread.start()
    
    # Wait for socket to become ready
    base_url = f"http://127.0.0.1:{port}"
    ready = False
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{base_url}/api/health", timeout=1.0) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            time.sleep(0.05)

    assert ready, "Server failed to start on port 8999"
    yield base_url
    server.stop()


def test_static_routes(live_server):
    # Test / (index.html)
    with urllib.request.urlopen(f"{live_server}/") as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type")
        body = resp.read().decode("utf-8")
        assert "YIELDIX COCKPIT" in body

    # Test /index.html
    with urllib.request.urlopen(f"{live_server}/index.html") as resp:
        assert resp.status == 200
        assert "YIELDIX COCKPIT" in resp.read().decode("utf-8")

    # Test /styles.css
    with urllib.request.urlopen(f"{live_server}/styles.css") as resp:
        assert resp.status == 200
        assert "text/css" in resp.headers.get("Content-Type")
        assert "--bg-core" in resp.read().decode("utf-8")

    # Test /app.js
    with urllib.request.urlopen(f"{live_server}/app.js") as resp:
        assert resp.status == 200
        assert "application/javascript" in resp.headers.get("Content-Type")
        assert "Yieldix Sovereign Cockpit" in resp.read().decode("utf-8")

    # Test /openapi.json
    with urllib.request.urlopen(f"{live_server}/openapi.json") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["openapi"] == "3.1.0"
        assert "/api/telemetry" in data["paths"]


def test_api_health(live_server):
    with urllib.request.urlopen(f"{live_server}/api/health") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] in ("HEALTHY", "CIRCUIT_BREAKER_SHEDDING")
        assert "uptime_seconds" in data
        assert "public_key" in data
        assert data["tenant_id"] == "sovereign-unicorn-demo"


def test_api_telemetry(live_server):
    with urllib.request.urlopen(f"{live_server}/api/telemetry") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "kpis" in data
        assert data["kpis"]["speed_to_lead_compliance_pct"] >= 0.0
        assert "cylinders" in data
        assert "c1_voice_receptionist" in data["cylinders"]
        assert "financial_metrics" in data
        assert data["financial_metrics"]["total_pipeline_evlp_usd"] > 0


def test_api_l2_queue_and_workflow(live_server):
    # Fetch queue
    with urllib.request.urlopen(f"{live_server}/api/l2-queue") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "pending_tasks" in data
        tasks = data["pending_tasks"]
        assert len(tasks) > 0
        task_id = tasks[0]["task_id"]

    # Approve task
    approve_payload = json.dumps({
        "task_id": task_id,
        "reviewer": "Test_SDR",
        "modified_body": "Updated custom text for verification."
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/l2-approve",
        data=approve_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        app_res = json.loads(resp.read().decode("utf-8"))
        assert app_res["status"] == "APPROVED"
        assert "ed25519_signature" in app_res

    # Try to approve already approved task (or non-pending)
    req_repeat = urllib.request.Request(
        f"{live_server}/api/l2-approve",
        data=approve_payload,
        headers={"Content-Type": "application/json"}
    )
    # The task was already approved, so it won't be pending in queue
    with urllib.request.urlopen(req_repeat) as resp:
        assert resp.status == 200

    # Reject task
    if len(tasks) > 1:
        task_to_reject = tasks[1]["task_id"]
        reject_payload = json.dumps({
            "task_id": task_to_reject,
            "reviewer": "Test_SDR",
            "reason": "Not in target ICP"
        }).encode("utf-8")
        req_rej = urllib.request.Request(
            f"{live_server}/api/l2-reject",
            data=reject_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req_rej) as resp:
            assert resp.status == 200
            rej_res = json.loads(resp.read().decode("utf-8"))
            assert rej_res["status"] == "REJECTED"


def test_api_l2_errors(live_server):
    # Missing task_id on approve
    req = urllib.request.Request(
        f"{live_server}/api/l2-approve",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400

    # Invalid task_id on approve
    req = urllib.request.Request(
        f"{live_server}/api/l2-approve",
        data=json.dumps({"task_id": "nonexistent-id-xyz"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 404

    # Missing task_id on reject
    req = urllib.request.Request(
        f"{live_server}/api/l2-reject",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400

    # Invalid task_id on reject
    req = urllib.request.Request(
        f"{live_server}/api/l2-reject",
        data=json.dumps({"task_id": "nonexistent-id-xyz"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 404


def test_api_competitors_and_sample_report(live_server):
    # Competitors
    with urllib.request.urlopen(f"{live_server}/api/competitors") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert len(data["competitors"]) >= 6

    # Sample Report
    with urllib.request.urlopen(f"{live_server}/api/sample-report") as resp:
        assert resp.status == 200
        report = json.loads(resp.read().decode("utf-8"))
        assert "signature_hex" in report
        assert "public_key_hex" in report
        assert "report_data" in report


def test_api_simulate(live_server):
    sim_payload = json.dumps({
        "leads": 2,
        "source": "WEB_INBOUND",
        "company": "Quantum Dynamics Corp"
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/simulate",
        data=sim_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["processed_count"] == 2


def test_api_circuit_breaker_toggle(live_server):
    # Trip
    trip_payload = json.dumps({"component": "C5_COLD_EMAIL", "action": "TRIP"}).encode("utf-8")
    req = urllib.request.Request(
        f"{live_server}/api/circuit-breaker/toggle",
        data=trip_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "C5_COLD_EMAIL" in data["shed_components"]
        assert data["is_active"] is False

    # Reset
    reset_payload = json.dumps({"component": "C5_COLD_EMAIL", "action": "RESET"}).encode("utf-8")
    req_res = urllib.request.Request(
        f"{live_server}/api/circuit-breaker/toggle",
        data=reset_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_res) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "C5_COLD_EMAIL" not in data["shed_components"]
        assert data["is_active"] is True


def test_api_verify_report(live_server):
    # Generate valid report
    with urllib.request.urlopen(f"{live_server}/api/sample-report") as resp:
        report = json.loads(resp.read().decode("utf-8"))

    verify_payload = json.dumps({
        "public_key_hex": report["public_key_hex"],
        "signature_hex": report["signature_hex"],
        "report_data": report["report_data"]
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{live_server}/api/verify-report",
        data=verify_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["valid"] is True
        assert "state_root_sha256" in data

    # Test with corrupted signature
    corrupt_payload = json.dumps({
        "public_key_hex": report["public_key_hex"],
        "signature_hex": "00" * 64,
        "report_data": report["report_data"]
    }).encode("utf-8")
    req_corrupt = urllib.request.Request(
        f"{live_server}/api/verify-report",
        data=corrupt_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_corrupt) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["valid"] is False

    # Missing parameters
    bad_req = urllib.request.Request(
        f"{live_server}/api/verify-report",
        data=b"{}",
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(bad_req)
    assert exc.value.code == 400


def test_server_error_and_cors_routes(live_server):
    # OPTIONS
    req_opt = urllib.request.Request(f"{live_server}/api/health", method="OPTIONS")
    with urllib.request.urlopen(req_opt) as resp:
        assert resp.status == 204

    # 404 GET
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"{live_server}/unknown-endpoint-xyz")
    assert exc.value.code == 404

    # 404 POST
    req_post_404 = urllib.request.Request(f"{live_server}/unknown-endpoint-xyz", data=b"{}")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req_post_404)
    assert exc.value.code == 404

    # Malformed JSON POST
    req_bad_json = urllib.request.Request(
        f"{live_server}/api/simulate",
        data=b"{not_json",
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req_bad_json)
    assert exc.value.code == 400


def test_server_lifecycle_and_static_fallback():
    from pathlib import Path

    from yieldix.server.app import YieldixAPIHandler, create_server

    # Non-blocking start and stop
    srv = create_server(host="127.0.0.1", port=8998)
    srv.start(blocking=False)
    srv.stop()

    # Direct test of _serve_static fallback on nonexistent path
    class DummyHandler:
        def __init__(self):
            self.status = None
            self.body = b""
        def _set_headers(self, mime, status):
            self.status = status
        @property
        def wfile(self):
            class WFile:
                def __init__(self, parent):
                    self.parent = parent
                def write(self, data):
                    self.parent.body += data
            return WFile(self)

    dummy = DummyHandler()
    YieldixAPIHandler._serve_static(dummy, Path("/nonexistent/file.html"), "text/html")
    assert dummy.status == 404
    assert b"Static file not found." in dummy.body


def test_server_keyboard_interrupt():
    import _thread
    import threading
    import time

    from yieldix.server.app import create_server

    srv = create_server(host="127.0.0.1", port=8993)

    def trigger_interrupt():
        time.sleep(0.08)
        _thread.interrupt_main()

    t = threading.Thread(target=trigger_interrupt, daemon=True)
    t.start()
    srv.start(blocking=True)
    t.join()
    assert srv._is_serving is False

