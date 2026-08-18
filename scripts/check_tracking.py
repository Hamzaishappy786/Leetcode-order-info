import asyncio
import json
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from playwright.async_api import async_playwright

TRACKING_NUMBER = "LI016551995CN"
ORDER_ID = "5097-1835-5123"
STATE_FILE = "state.json"
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT = os.environ.get("RECIPIENT_EMAIL", GMAIL_USER)

CHECKPOINT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}")


async def get_page_text():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(
            f"https://t.17track.net/en#nums={TRACKING_NUMBER}",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await page.wait_for_timeout(8000)
        text = await page.inner_text("body")
        await browser.close()
    return text


def parse(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    checkpoints = [l for l in lines if CHECKPOINT_RE.match(l)]
    status = next(
        (l for l in lines if any(k in l for k in ("In transit", "Delivered", "Out for Delivery", "Pick up", "Undelivered"))),
        "Unknown",
    )
    return checkpoints, status


def load_state():
    p = Path(STATE_FILE)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            return {"lastTopLine": data.get("lastTopLine", "")}
        except Exception:
            pass
    return {"lastTopLine": ""}


def save_state(top_line):
    Path(STATE_FILE).write_text(json.dumps({"lastTopLine": top_line}, indent=2))


def split_carriers(checkpoints):
    pk, cn = [], []
    for c in checkpoints:
        lower = c.lower()
        if any(k in lower for k in ("guangzhou ems", "pakistan post", "islamabad", "karachi", "lahore")):
            pk.append(c)
        else:
            cn.append(c)
    return pk, cn


def checkpoint_rows(items, highlight_first=False):
    rows = ""
    for i, item in enumerate(items):
        parts = item.split(" ", 2)
        time = f"{parts[0]} {parts[1]}" if len(parts) >= 2 else item
        desc = parts[2] if len(parts) >= 3 else ""
        dot_color = "#1a1a2e" if (i == 0 and highlight_first) else "#d1d5db"
        rows += f"""
        <tr>
          <td style="padding:8px 12px 8px 0;vertical-align:top;white-space:nowrap;font-size:11px;color:#94a3b8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">{time}</td>
          <td style="padding:8px 0 8px 12px;vertical-align:top;">
            <div style="display:flex;align-items:flex-start;gap:10px;">
              <div style="width:8px;height:8px;border-radius:50%;background:{dot_color};margin-top:4px;flex-shrink:0;"></div>
              <span style="font-size:13px;color:#374151;line-height:1.4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">{desc}</span>
            </div>
          </td>
        </tr>"""
    return rows


def build_html(top, status, checkpoints):
    pk, cn = split_carriers(checkpoints)
    if not pk:
        pk = checkpoints[:3]
    if not cn:
        cn = checkpoints[3:]

    pk_rows = checkpoint_rows(pk, highlight_first=True)
    cn_rows = checkpoint_rows(cn)

    carrier_section = ""
    if pk_rows:
        carrier_section += f"""
        <div style="padding:0 28px 20px;">
          <div style="font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:12px;padding-bottom:8px;border-bottom:0.5px solid #e5e7eb;">Pakistan Post</div>
          <table style="width:100%;border-collapse:collapse;">{pk_rows}</table>
        </div>"""
    if cn_rows:
        carrier_section += f"""
        <div style="padding:0 28px 20px;">
          <div style="font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:12px;padding-bottom:8px;border-bottom:0.5px solid #e5e7eb;">China Post</div>
          <table style="width:100%;border-collapse:collapse;">{cn_rows}</table>
        </div>"""

    top_parts = top.split(" ", 2)
    top_time = f"{top_parts[0]} {top_parts[1]}" if len(top_parts) >= 2 else top
    top_desc = top_parts[2] if len(top_parts) >= 3 else top

    track_url = f"https://t.17track.net/en#nums={TRACKING_NUMBER}"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:560px;margin:24px auto;padding:0 16px;">
    <div style="background:#ffffff;border-radius:12px;overflow:hidden;border:0.5px solid #e0e0e0;">

      <!-- Header -->
      <div style="background:#1a1a2e;padding:28px 28px 20px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
          <div style="width:36px;height:36px;background:#f89f1b;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;color:#1a1a2e;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">LC</div>
          <span style="color:#ffffff;font-size:14px;font-weight:500;opacity:0.9;">LeetCode Order Tracker</span>
        </div>
        <div style="display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.2);border-radius:20px;padding:4px 12px;margin-bottom:10px;">
          <div style="width:7px;height:7px;border-radius:50%;background:#4ade80;"></div>
          <span style="color:#4ade80;font-size:12px;font-weight:500;letter-spacing:0.5px;">{status}</span>
        </div>
        <div style="color:#ffffff;font-size:20px;font-weight:600;margin:0 0 4px;">Your T-shirt is on the way</div>
        <div style="color:rgba(255,255,255,0.55);font-size:13px;">Order {ORDER_ID} &middot; {TRACKING_NUMBER}</div>
      </div>

      <!-- Latest update box -->
      <div style="margin:20px 28px;background:#f0f7ff;border:1px solid #bfdbfe;border-radius:10px;padding:14px 16px;display:flex;gap:12px;align-items:flex-start;">
        <div style="font-size:20px;line-height:1;">📦</div>
        <div>
          <div style="font-size:11px;font-weight:600;color:#185fa5;text-transform:uppercase;letter-spacing:0.6px;margin-bottom:3px;">Latest update</div>
          <div style="font-size:14px;color:#0c447c;font-weight:500;">{top_time} &mdash; {top_desc}</div>
        </div>
      </div>

      <!-- Route -->
      <div style="margin:0 28px 20px;display:flex;align-items:center;gap:8px;">
        <span style="font-size:13px;font-weight:500;color:#444;">&#127464;&#127475; China</span>
        <div style="flex:1;height:1px;background:#e2e8f0;"></div>
        <span style="font-size:13px;color:#64748b;">&#9992;</span>
        <div style="flex:1;height:1px;background:#e2e8f0;"></div>
        <span style="font-size:13px;font-weight:500;color:#444;">&#127477;&#127472; Pakistan</span>
      </div>

      <!-- Carrier sections -->
      {carrier_section}

      <!-- Footer -->
      <div style="background:#f9fafb;border-top:0.5px solid #e5e7eb;padding:16px 28px;display:flex;align-items:center;justify-content:space-between;">
        <span style="font-size:11px;color:#9ca3af;">Automated alert &middot; checks every 6 hours</span>
        <a href="{track_url}" style="background:#1a1a2e;color:#ffffff;font-size:12px;font-weight:500;padding:8px 16px;border-radius:6px;text-decoration:none;">Track live &rarr;</a>
      </div>

    </div>
  </div>
</body>
</html>"""


def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)


async def main():
    print("Fetching tracking page...")
    text = await get_page_text()
    checkpoints, status = parse(text)

    if not checkpoints:
        print("No checkpoints found — page may not have loaded properly.")
        return

    top = checkpoints[0]
    state = load_state()

    save_state(top)

    print(f"Last known:  '{state['lastTopLine']}'")
    print(f"Current top: '{top}'")
    if top == state["lastTopLine"]:
        print("No change — skipping email.")
        return

    print(f"Last known: '{state['lastTopLine']}'")
    print(f"New update detected: {top}")

    html = build_html(top, status, checkpoints)
    send_email(f"Order update: LeetCode T-Shirt — {top}", html)
    print("Email sent!")


asyncio.run(main())
