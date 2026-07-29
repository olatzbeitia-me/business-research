#!/usr/bin/env python3
"""Send a business-research report by email — fully auto, no manual click.

Why this exists
---------------
The Gmail integration used elsewhere in this project can only create *drafts*,
not send. This script is the send-capable path so scheduled runs can email the
full refreshed content automatically.

It supports two transports and picks whichever credential is present:

1. HTTPS email API (Resend)  -> works inside the locked-down web environment
   (outbound is HTTPS-only; raw SMTP sockets are blocked here).
   Env: RESEND_API_KEY   [optional: NOTIFY_FROM, NOTIFY_TO]

2. Gmail SMTP + App Password -> works anywhere SMTP egress is allowed
   (e.g. your own computer). Sends *through* your Gmail.
   Env: GMAIL_ADDRESS, GMAIL_APP_PASSWORD   [optional: NOTIFY_TO]

If neither credential is set, it exits non-zero with setup instructions so the
caller can fall back to creating a Gmail draft instead.

Usage
-----
    python3 scripts/send_report_email.py \
        --subject "Business Model Scan — 2026-07-29" \
        --html-file notifications/2026-07-29.html \
        [--text-file notifications/2026-07-29.txt] \
        [--to you@example.com] [--from bot@yourdomain.com] [--dry-run]

Stdlib only — no pip installs, so it runs reliably in ephemeral environments.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.request
from email.message import EmailMessage
from html.parser import HTMLParser

DEFAULT_TO = os.environ.get("NOTIFY_TO", "olatzbeitia@gmail.com")
# Resend's onboarding sender works out-of-the-box for emailing your own account.
# Once you verify a domain in Resend, set NOTIFY_FROM to e.g. bot@yourdomain.com.
DEFAULT_FROM = os.environ.get("NOTIFY_FROM", "onboarding@resend.dev")
RESEND_ENDPOINT = "https://api.resend.com/emails"
# A real User-Agent — the default "Python-urllib/x" is blocked by Cloudflare (err 1010).
USER_AGENT = "business-research-notifier/1.0 (+https://github.com/olatzbeitia-me/business-research)"


# ----------------------------------------------------------------------------- helpers
class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(html: str) -> str:
    """Very small HTML->text fallback for the plaintext alternative part."""
    s = _Stripper()
    s.feed(html)
    text = "".join(s.parts)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _ca_bundle() -> str | None:
    """Find a CA bundle that trusts the environment's HTTPS proxy, if any."""
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        p = os.environ.get(var)
        if p and os.path.exists(p):
            return p
    for p in ("/root/.ccr/ca-bundle.crt",):  # known proxy CA in web sessions
        if os.path.exists(p):
            return p
    return None


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ca = _ca_bundle()
    if ca:
        try:
            ctx.load_verify_locations(ca)
        except Exception:
            pass
    return ctx


def _https_opener() -> urllib.request.OpenerDirector:
    """Opener that honours HTTPS_PROXY and trusts the proxy CA."""
    handlers: list[urllib.request.BaseHandler] = [
        urllib.request.HTTPSHandler(context=_ssl_context())
    ]
    proxies = urllib.request.getproxies()  # reads HTTPS_PROXY / https_proxy
    if proxies:
        handlers.append(urllib.request.ProxyHandler(proxies))
    return urllib.request.build_opener(*handlers)


# ----------------------------------------------------------------------------- transports
def send_via_resend(api_key: str, frm: str, to: str, subject: str,
                    html: str, text: str) -> None:
    payload = json.dumps({
        "from": frm,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }).encode("utf-8")
    req = urllib.request.Request(
        RESEND_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with _https_opener().open(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "replace")
        if resp.status >= 300:
            raise RuntimeError(f"Resend API error {resp.status}: {body}")
        print(f"Sent via Resend to {to}. Response: {body}")


def send_via_smtp(address: str, app_password: str, frm: str, to: str,
                  subject: str, html: str, text: str) -> None:
    import smtplib  # imported lazily; unavailable path in HTTPS-only envs

    msg = EmailMessage()
    msg["From"] = frm or address
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(address, app_password)
        server.send_message(msg)
    print(f"Sent via Gmail SMTP ({address}) to {to}.")


# ----------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description="Send a report by email (auto-send).")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--html-file", required=True,
                    help="Path to the HTML email body.")
    ap.add_argument("--text-file",
                    help="Optional plaintext alternative; derived from HTML if omitted.")
    ap.add_argument("--to", default=DEFAULT_TO)
    ap.add_argument("--from", dest="frm", default=DEFAULT_FROM)
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate + print without sending.")
    args = ap.parse_args()

    with open(args.html_file, encoding="utf-8") as fh:
        html = fh.read()
    if args.text_file:
        with open(args.text_file, encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = html_to_text(html)

    resend_key = os.environ.get("RESEND_API_KEY")
    gmail_addr = os.environ.get("GMAIL_ADDRESS")
    gmail_pw = os.environ.get("GMAIL_APP_PASSWORD")

    if resend_key:
        transport = "resend"
    elif gmail_addr and gmail_pw:
        transport = "smtp"
    else:
        sys.stderr.write(
            "No email credential found — cannot auto-send.\n"
            "Set ONE of the following (see notifications/README.md):\n"
            "  RESEND_API_KEY            (HTTPS API — works in the web environment)\n"
            "  GMAIL_ADDRESS + GMAIL_APP_PASSWORD  (Gmail SMTP — local/other envs)\n"
            "Falling back is the caller's job (e.g. create a Gmail draft).\n"
        )
        return 3

    print(f"transport={transport} to={args.to} from={args.frm} "
          f"subject={args.subject!r} html_bytes={len(html)}")
    if args.dry_run:
        print("[dry-run] not sending.")
        print("--- text preview (first 500 chars) ---")
        print(text[:500])
        return 0

    if transport == "resend":
        send_via_resend(resend_key, args.frm, args.to, args.subject, html, text)
    else:
        send_via_smtp(gmail_addr, gmail_pw, args.frm, args.to, args.subject, html, text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
