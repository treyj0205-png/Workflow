"""Find the top 5 moving US stocks of the day, explain why, and push a notification.

Env vars:
  ANTHROPIC_API_KEY  required for company descriptions and "why it's moving"
  NTFY_TOPIC         push notification via ntfy.sh (install the ntfy app, subscribe to this topic)
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_TO   optional email delivery
  MIN_PRICE (5), MIN_MARKET_CAP (500000000), MIN_VOLUME (1000000), TOP_N (5)
  DRY_RUN=1          print only, do not send
"""
import os
import smtplib
import sys
from email.message import EmailMessage

import requests
import yfinance as yf
from yfinance import EquityQuery

MIN_PRICE = float(os.getenv("MIN_PRICE", 5))
MIN_CAP = float(os.getenv("MIN_MARKET_CAP", 500_000_000))
MIN_VOL = float(os.getenv("MIN_VOLUME", 1_000_000))
TOP_N = int(os.getenv("TOP_N", 5))
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")


def get_movers():
    q = EquityQuery("and", [
        EquityQuery("eq", ["region", "us"]),
        EquityQuery("is-in", ["exchange", "NMS", "NYQ"]),
        EquityQuery("gt", ["intradayprice", MIN_PRICE]),
        EquityQuery("gt", ["intradaymarketcap", MIN_CAP]),
        EquityQuery("gt", ["dayvolume", MIN_VOL]),
    ])
    res = yf.screen(q, sortField="percentchange", sortAsc=False, size=TOP_N)
    return res.get("quotes", [])[:TOP_N]


def get_headlines(symbol, limit=6):
    try:
        out = []
        for item in yf.Ticker(symbol).news[:limit]:
            c = item.get("content", item)
            title = c.get("title")
            summary = c.get("summary") or ""
            if title:
                out.append(f"- {title}. {summary[:200]}".strip())
        return out
    except Exception:
        return []


def explain(quote, headlines):
    """Return (description, reason) from Claude, grounded in the headlines supplied."""
    import anthropic
    client = anthropic.Anthropic()
    prompt = (
        f"Ticker: {quote['symbol']} ({quote.get('shortName', '')})\n"
        f"Move today: {quote.get('regularMarketChangePercent', 0):+.1f}% to "
        f"${quote.get('regularMarketPrice', 0):.2f}, volume {quote.get('regularMarketVolume', 0):,}\n"
        f"Recent headlines:\n" + ("\n".join(headlines) or "(none found)") + "\n\n"
        "Reply in exactly two lines:\n"
        "WHAT: one sentence on what the company does.\n"
        "WHY: one or two sentences on why the stock is moving today, based only on the headlines above. "
        "If the headlines do not explain it, write 'No clear catalyst found in news' and say what is "
        "known (e.g. sector move, volume spike). Do not speculate."
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=300, messages=[{"role": "user", "content": prompt}]
    )
    text = msg.content[0].text
    what = why = ""
    for line in text.splitlines():
        if line.upper().startswith("WHAT:"):
            what = line[5:].strip()
        elif line.upper().startswith("WHY:"):
            why = line[4:].strip()
    return what or text.strip(), why


def build_message(movers):
    lines = []
    for i, q in enumerate(movers, 1):
        what, why = explain(q, get_headlines(q["symbol"]))
        lines.append(
            f"{i}. {q['symbol']} {q.get('regularMarketChangePercent', 0):+.1f}% "
            f"(${q.get('regularMarketPrice', 0):.2f})\n"
            f"   {what}\n   Why: {why}"
        )
    return "\n\n".join(lines)


def send_ntfy(title, body):
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return False
    r = requests.post(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
                      headers={"Title": title, "Tags": "chart_with_upwards_trend"}, timeout=20)
    r.raise_for_status()
    return True


def send_email(title, body):
    host, to = os.getenv("SMTP_HOST"), os.getenv("EMAIL_TO")
    if not (host and to):
        return False
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = title, os.environ["SMTP_USER"], to
    m.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(m)
    return True


def main():
    movers = get_movers()
    if not movers:
        print("No movers matched filters.")
        return 1
    title = f"Top {len(movers)} movers today"
    body = build_message(movers)
    print(title + "\n\n" + body)
    if os.getenv("DRY_RUN"):
        return 0
    sent = [send_ntfy(title, body), send_email(title, body)]
    if not any(sent):
        print("No delivery channel configured (set NTFY_TOPIC or SMTP_*).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
