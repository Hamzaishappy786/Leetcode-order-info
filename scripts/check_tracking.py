import asyncio
import json
import os
import re
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from playwright.async_api import async_playwright

TRACKING_NUMBER = "LI016551995CN"
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
        return json.loads(p.read_text())
    return {"lastTopLine": ""}


def save_state(top_line):
    Path(STATE_FILE).write_text(json.dumps({"lastTopLine": top_line}, indent=2))


def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT
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

    if top == state["lastTopLine"]:
        print(f"No change. Last known: {top}")
        return

    print(f"New update detected: {top}")

    body = f"""New tracking update for your LeetCode T-Shirt (Order 5097-1835-5123)

Latest checkpoint: {top}
Status: {status}

Full history:
{chr(10).join(checkpoints)}

Track live: https://t.17track.net/en#nums={TRACKING_NUMBER}
"""
    send_email(f"Order update: LeetCode T-Shirt — {top}", body)
    print("Email sent!")


asyncio.run(main())
