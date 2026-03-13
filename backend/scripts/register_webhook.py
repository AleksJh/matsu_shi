"""One-time script to register the Telegram Bot webhook.

Usage (run from backend/ directory):
    python scripts/register_webhook.py
    python scripts/register_webhook.py --url https://your-domain.com/webhook
    python scripts/register_webhook.py --url https://your-domain.com/webhook --secret <token>
    python scripts/register_webhook.py --delete   # remove webhook (switch to polling)
"""
from __future__ import annotations

import argparse
import sys

import httpx

# Must be run from backend/ so .env and app imports resolve correctly
from app.core.config import settings

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _api_url(method: str) -> str:
    return TELEGRAM_API_BASE.format(token=settings.BOT_TOKEN, method=method)


def set_webhook(url: str, secret: str) -> None:
    payload: dict = {"url": url}
    if secret:
        payload["secret_token"] = secret

    resp = httpx.post(_api_url("setWebhook"), json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("ok"):
        print(f"Webhook set successfully: {data.get('description', 'OK')}")
    else:
        print(f"Failed to set webhook: {data}", file=sys.stderr)
        sys.exit(1)


def delete_webhook() -> None:
    resp = httpx.post(_api_url("deleteWebhook"), timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("ok"):
        print("Webhook deleted (bot will use polling).")
    else:
        print(f"Failed to delete webhook: {data}", file=sys.stderr)
        sys.exit(1)


def get_webhook_info() -> None:
    resp = httpx.get(_api_url("getWebhookInfo"), timeout=15)
    resp.raise_for_status()
    info = resp.json().get("result", {})
    webhook_url = info.get("url", "(none)")
    pending = info.get("pending_update_count", 0)
    last_error = info.get("last_error_message", "")
    print(f"Current webhook URL : {webhook_url}")
    print(f"Pending updates     : {pending}")
    if last_error:
        print(f"Last error          : {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register or remove the Telegram webhook for Matsu Shi bot."
    )
    parser.add_argument(
        "--url",
        default=None,
        help=(
            "Webhook URL to register. Defaults to {APP_BASE_URL}/webhook "
            "from .env if not provided."
        ),
    )
    parser.add_argument(
        "--secret",
        default=settings.WEBHOOK_SECRET,
        help="Webhook secret token (WEBHOOK_SECRET from .env by default).",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Remove the webhook instead of setting it.",
    )
    args = parser.parse_args()

    if args.delete:
        delete_webhook()
    else:
        url = args.url or f"{settings.APP_BASE_URL.rstrip('/')}/webhook"
        if not url.startswith("https://"):
            print(
                f"Warning: Telegram requires HTTPS webhook URLs. Got: {url}",
                file=sys.stderr,
            )
        set_webhook(url, args.secret)

    print()
    get_webhook_info()


if __name__ == "__main__":
    main()
