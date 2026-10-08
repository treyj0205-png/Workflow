# Top movers notifier

Daily push with the top 5 US stock movers, a one-line company description, and why each is moving.

Pipeline: Yahoo screener (via yfinance) -> recent headlines per ticker -> Claude writes WHAT/WHY from those headlines -> ntfy push and/or email.

Defaults filter out junk: price > $5, market cap > $500M, volume > 1M. Override with `MIN_PRICE`, `MIN_MARKET_CAP`, `MIN_VOLUME`, `TOP_N`.

## Setup
1. Install the ntfy app, subscribe to a hard-to-guess topic name.
2. Repo secrets: `ANTHROPIC_API_KEY`, `NTFY_TOPIC` (and optionally `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_TO`).
3. Actions > Top movers > Run workflow to test. Schedule is 4:15pm ET weekdays; edit the cron in `.github/workflows/daily.yml`.

Local test: `pip install -r requirements.txt && DRY_RUN=1 ANTHROPIC_API_KEY=... python movers.py`
