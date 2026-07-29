# Email notifications — setup (one-time)

The bot can **auto-send** each update to your inbox (no clicking). It uses
[`scripts/send_report_email.py`](../scripts/send_report_email.py), which needs
**one credential** you add once. Pick the option that matches where it runs.

You only need to do **ONE** of the two below.

---

## Option A — Resend (recommended; works in the Claude Code web environment)

The web environment only allows outbound HTTPS, so Gmail's SMTP is blocked there.
Resend sends over HTTPS, so it works. Free tier = 3,000 emails/month (plenty).

1. Go to **resend.com** and sign up **with your Gmail address** (olatzbeitia@gmail.com).
   Signing up with that address lets you send to yourself immediately using their
   built-in `onboarding@resend.dev` sender — no domain setup needed.
2. In the Resend dashboard: **API Keys → Create API Key** (name it e.g. "business-research"). Copy it (starts with `re_...`).
3. Add it to the environment as a variable named **`RESEND_API_KEY`**:
   - In Claude Code on the web, open your environment's settings and add an
     environment variable / secret: `RESEND_API_KEY = re_xxxxxxxx`.
     (See the env-config section of https://code.claude.com/docs/en/claude-code-on-the-web)
4. Done. The next update will email itself automatically.

*Optional, later:* if you verify your own domain in Resend, set `NOTIFY_FROM`
to e.g. `bot@yourdomain.com` so the email comes "from" you rather than
`onboarding@resend.dev`.

---

## Option B — Gmail App Password (sends *through* your Gmail; for your own computer)

Use this if you run the script somewhere that allows SMTP (e.g. your laptop).
It won't work in the web environment (SMTP is blocked there).

1. Turn on **2-Step Verification** on your Google account (required for App Passwords).
2. Go to **myaccount.google.com → Security → App passwords**, create one for "Mail". Copy the 16-character password.
3. Set two environment variables:
   - `GMAIL_ADDRESS = olatzbeitia@gmail.com`
   - `GMAIL_APP_PASSWORD = the 16-char app password` (no spaces)
4. Done — emails send from your Gmail.

---

## How it runs

```bash
python3 scripts/send_report_email.py \
    --subject "Business Model Scan — 2026-07-29" \
    --html-file notifications/2026-07-29.html
```

- Recipient defaults to `olatzbeitia@gmail.com` (override with `--to` or `NOTIFY_TO`).
- The script auto-picks the transport: `RESEND_API_KEY` if set, otherwise Gmail SMTP.
- If **no** credential is set, it exits without sending and the bot falls back to
  leaving a ready-to-send **Gmail draft** instead (so you never miss an update).
- Add `--dry-run` to preview without sending.

## Security
- Never commit keys. They live only as environment variables/secrets.
- The App Password / API key can be revoked anytime from Google / Resend.
