#!/usr/bin/env python3
"""yieldix MCP sunucusu - Model Context Protocol 2025-06-18 over stdio.

Yieldix B2B-revenue-engine'inin bagimsiz-dogrulama ve durum-cekirdegini
AI ajanlarina MCP araclari olarak sunar. Tamga/sester/pacta MCP
sunucularinin ayni deseni ( stdio JSON-RPC, uc-sonuc kaniti,
exception-YOK).

Tasarim-ilkesi:
  - SAF STDLIB - hicbir pip bagimliligi; sunucu yieldix CLI'ini
    SUBPROCESS-LEVEL'da cagirir, import etmez - surum-cakismasi yok.
  - UC-SONUC - her arac GREEN/RED/INDETERMINE JSON kaniti dondurur;
    ASLA exception firlatmaz.
  - Bagimsiz-dogrulama - verify araci lead->silindir->KPI->imzali-rapor
    zincirini sifirdan-oynar ( paylasilan-demo-durumu-KULLANMAZ).

Araclar:
  status      motor + devre-kesici-durumu ( yieldix status)
  verify      bagimsiz-dogrulama ( yieldix verify --tenant)

Calistirma:
  python3 mcp/server.py                    # stdio JSON-RPC
  (istemci tarafi: "command": "python", "args": ["<repo>/mcp/server.py"])
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "yieldix"
SERVER_VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parents[1]
MAX_TIMEOUT = 120  # saniye


def _e(msg: str) -> dict:
    return {"jsonrpc": "2.0", "error": {"code": -32602, "message": msg}}


def _result(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _text(payload: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def _env() -> dict:
    """yieldix src-layout-oldugu-icin PYTHONPATH=src gerekiyor.

    Bu, yieldix'in KENDI kurulum-dokumantasyonuyla-ayni ( pip install -e .
    da ayni-etkiyi-yapar). MCP sunucusu modulu import-ETMEZ, sadece
    alt-subprocess'i dogru-cevreye-sahip-olacak-sekilde-baslatir.
    """
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    src = str(ROOT / "src")
    if src not in existing.split(os.pathsep):
        env["PYTHONPATH"] = src + (os.pathsep + existing if existing else "")
    return env


def _run_cli(args: list) -> dict:
    """yieldix CLI'ini SUBPROCESS olarak cagir, cikisini JSON kanita cevir.

    Fail-closed: her hata ( zaman-asimi, exception, bozuk-cikis) bir RED
    kanitidir - traceback DEGIL, JSON doner. CLI insan-okunur cikti-basar;
    rc + cikis JSON kanitina-sarilir.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "yieldix.cli.main", *args],
            capture_output=True, text=True, timeout=MAX_TIMEOUT, cwd=str(ROOT),
            env=_env())
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "zaman-asimi: %ds" % MAX_TIMEOUT}
    except Exception as e:  # cephedeki her hata JSON kaniti olmali
        return {"ok": False, "reason": "calistirma-hatasi: %s" % e}
    out = (proc.stdout or "").strip()
    return {
        "ok": proc.returncode == 0,
        "rc": proc.returncode,
        "report": out[:2000],
        "stderr": (proc.stderr or "").strip()[:300],
    }


def _tool_status(args: dict) -> dict:
    return _run_cli(["status"])


def _tool_verify(args: dict) -> dict:
    """Bagimsiz-dogrulama - her-geçidi-ayrı-ölçer ( args.tenant opsiyonel)."""
    cli_args = ["verify"]
    tenant = args.get("tenant")
    if isinstance(tenant, str) and tenant:
        cli_args += ["--tenant", tenant]
    return _run_cli(cli_args)


TOOL_IMPLS = {
    "status": _tool_status,
    "verify": _tool_verify,
}

TOOLS_LIST = [
    {
        "name": "status",
        "description": (
            "Yieldix motorunun ve devre-kesicinin ( circuit-breaker) "
            "durumunu gosterir: aktif-bilesenler, shed-edilenler. "
            "JSON kanit doner."),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "verify",
        "description": (
            "Bagimsiz-dogrulama: lead -> silindirler -> KPI -> imzali-rapor "
            "zincirini sifirdan-oynar ve Ed25519-imzasini yeniden-dogrular. "
            "Demo-komutlarinin-paylastigi-durumu-KULLANMAZ. "
            "args.tenant opsiyonel ( varsayilan: cust_enterprise_01)."),
        "inputSchema": {
            "type": "object",
            "properties": {"tenant": {"type": "string"}},
            "additionalProperties": False,
        },
    },
]


def _tools_list_result() -> dict:
    return {"tools": TOOLS_LIST}


def _handle_call(req_id, params: dict) -> dict | None:
    name = params.get("name")
    if not isinstance(name, str) or not name:
        return _result(req_id, _e("arac-adi-zorunlu"))
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {
            "jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": "bilinmeyen-arac: %s" % name},
        }
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        return _result(req_id, _e("arguments-bir-nesne-olmali"))
    try:
        payload = impl(args)
    except Exception as e:  # fail-closed: traceback degil JSON kaniti
        payload = {"ok": False, "reason": "arac-hatasi: %s" % e}
    return _result(req_id, _text(payload))


def main() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_e("gecersiz-json")) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(req, dict):
            sys.stdout.write(json.dumps(_e("istek-bir-nesne-degil")) + "\n")
            sys.stdout.flush()
            continue
        method = req.get("method")
        req_id = req.get("id")
        if method == "initialize":
            sys.stdout.write(json.dumps(_result(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                    "instructions": (
                        "Yieldix B2B-revenue-engine sunucusu. "
                        "status -> motor-durumu; verify -> bagimsiz-dogrulama. "
                        "Her arac JSON kaniti doner, asla exception firlatmaz."),
                }})) + "\n")
        elif method == "notifications/initialized":
            continue  # bildirim - yanit yok
        elif method == "tools/list":
            sys.stdout.write(json.dumps(_result(req_id, _tools_list_result())) + "\n")
        elif method == "tools/call":
            resp = _handle_call(req_id, req.get("params") or {})
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        elif method == "ping":
            sys.stdout.write(json.dumps(_result(req_id, {})) + "\n")
        elif req_id is not None:
            sys.stdout.write(json.dumps({
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": "bilinmeyen-method: %s" % method}
            }) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
