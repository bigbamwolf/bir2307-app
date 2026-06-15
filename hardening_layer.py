"""
Hardening Layer
Shipped 2026-06-13 hardening pass, extended 2026-06-16.

Two purposes:
  1. Inject CSP + X-Content-Type-Options + Referrer + an in-house Sentry
     IIFE into the Streamlit page head, so XSS surface and base-uri attacks
     are clipped and frontend errors fan out to Boss's Cams Bot Telegram.
  2. Install a Python sys.excepthook that POSTs catastrophic backend
     exceptions to the same arwin-payments sentry_log endpoint.

Call inject_hardening("bir2307") near the top of app.py, right after
st.set_page_config. Idempotent, safe to call on every rerun.
"""

from __future__ import annotations

import json
import sys
import traceback
import urllib.request
from typing import Optional

import streamlit as st

SENTRY_ENDPOINT = "https://script.google.com/macros/s/AKfycbzvfiPw3pIlPAbVY9syj8Lt3Bi2vbM-G8WIGCWxt9u9Z_MG8yGcy8He1I_sQCb-kw-dzg/exec"

_HEAD_BLOCK_TMPL = """
<meta http-equiv="Content-Security-Policy" content="default-src 'self' https: data: blob: 'unsafe-inline' 'unsafe-eval'; object-src 'none'; base-uri 'self'">
<meta http-equiv="X-Content-Type-Options" content="nosniff">
<meta name="referrer" content="strict-origin-when-cross-origin">
<script>
(function(){
  if (window.__hardeningOn) return;
  window.__hardeningOn = true;
  var EP = "__EP__", S = "__SRC__";
  function rep(p){
    try {
      fetch(EP, {
        method: "POST", mode: "no-cors",
        headers: {"Content-Type": "text/plain"},
        body: JSON.stringify(Object.assign({route: "sentry_log", source: S}, p))
      });
    } catch(e){}
  }
  window.addEventListener("error", function(e){
    rep({message: String(e.message || "err"), stack: String((e.error && e.error.stack) || ""), url: location.href, ua: navigator.userAgent, type: "error"});
  });
  window.addEventListener("unhandledrejection", function(e){
    rep({message: String((e.reason && e.reason.message) || e.reason || "reject"), stack: String((e.reason && e.reason.stack) || ""), url: location.href, ua: navigator.userAgent, type: "reject"});
  });
})();
</script>
"""

_PY_HANDLER_INSTALLED = False


def _post_server_error(source: str, exc_type, exc_value, exc_tb) -> None:
    try:
        payload = {
            "route": "sentry_log",
            "source": f"{source}-backend",
            "message": f"{exc_type.__name__}: {exc_value}"[:600],
            "stack": "".join(traceback.format_tb(exc_tb))[:2000],
            "type": "uncaught",
            "ua": "python",
            "url": "streamlit",
        }
        req = urllib.request.Request(
            SENTRY_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=4) as r:
            r.read()
    except Exception:
        pass


def _install_python_handler(source: str) -> None:
    global _PY_HANDLER_INSTALLED
    if _PY_HANDLER_INSTALLED:
        return
    prior = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        _post_server_error(source, exc_type, exc_value, exc_tb)
        if prior is not None:
            prior(exc_type, exc_value, exc_tb)

    sys.excepthook = hook
    _PY_HANDLER_INSTALLED = True


def inject_hardening(source: str) -> None:
    """Call once near the top of app.py (after st.set_page_config).

    source identifies the calling Streamlit app in Sentry payloads, e.g.
    "supplier-portal", "supplier-accreditation", "bir2307".
    """
    _install_python_handler(source)
    if st.session_state.get("_hardening_injected"):
        return
    head_block = _HEAD_BLOCK_TMPL.replace("__EP__", SENTRY_ENDPOINT).replace("__SRC__", source)
    st.markdown(head_block, unsafe_allow_html=True)
    st.session_state["_hardening_injected"] = True


def report_backend_error(source: str, exc: BaseException, context: Optional[dict] = None) -> None:
    """Call from inside try/except blocks where you want telemetry without
    propagating the exception to sys.excepthook."""
    ctx = context or {}
    try:
        payload = {
            "route": "sentry_log",
            "source": f"{source}-backend",
            "message": f"{type(exc).__name__}: {exc}"[:600],
            "stack": "".join(traceback.format_tb(exc.__traceback__))[:2000],
            "type": ctx.get("type", "caught"),
            "ua": "python",
            "url": str(ctx.get("url", "streamlit")),
        }
        req = urllib.request.Request(
            SENTRY_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=4) as r:
            r.read()
    except Exception:
        pass
