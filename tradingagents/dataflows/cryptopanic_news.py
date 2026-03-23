"""CryptoPanic API news fetching for crypto assets."""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import Annotated


CRYPTOPANIC_API_BASE = "https://cryptopanic.com/api/v1/posts/"


def _get_api_key() -> str:
    api_key = os.getenv("CRYPTOPANIC_API_KEY")
    if not api_key:
        raise ValueError("CRYPTOPANIC_API_KEY environment variable is not set.")
    return api_key


def _parse_currency(ticker: str) -> str:
    """Extract base currency from a ticker.
    Accepts BTC/USDT, BTC-USDT, BTC, bitcoin, etc.
    Returns the uppercase base currency code.
    """
    for sep in ["/", "-", "_"]:
        if sep in ticker:
            return ticker.split(sep)[0].upper()
    return ticker.upper()


def _sentiment_label(votes: dict) -> str:
    """Derive a simple sentiment label from CryptoPanic vote counts."""
    positive = votes.get("positive", 0) + votes.get("liked", 0)
    negative = votes.get("negative", 0) + votes.get("disliked", 0)
    if positive > negative * 1.5:
        return "Bullish"
    elif negative > positive * 1.5:
        return "Bearish"
    return "Neutral"


def _fetch_posts(params: dict, start_date: str, max_pages: int = 5) -> list:
    """
    Paginate CryptoPanic API until results fall before start_date or max_pages is reached.
    Returns a list of article dicts.
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    articles = []
    url = CRYPTOPANIC_API_BASE

    for _ in range(max_pages):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            break

        results = data.get("results", [])
        if not results:
            break

        for item in results:
            created_raw = item.get("published_at") or item.get("created_at", "")
            try:
                created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except (ValueError, AttributeError):
                created_dt = None

            articles.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", {}).get("title", "Unknown"),
                "created_at": created_dt,
                "votes": item.get("votes", {}),
                "currencies": [c.get("code", "") for c in item.get("currencies", [])],
            })

        # Stop paginating if oldest article on this page is already before start_date
        oldest = articles[-1]["created_at"]
        if oldest and oldest < start_dt:
            break

        next_url = data.get("next")
        if not next_url:
            break
        # On subsequent pages, params are encoded in the URL already
        url = next_url
        params = {}

    return articles


def _format_articles(articles: list, start_date: str, end_date: str) -> list[str]:
    """Filter articles to date range and format each as a markdown string."""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

    lines = []
    for a in articles:
        dt = a["created_at"]
        if dt and not (start_dt <= dt < end_dt):
            continue
        date_str = dt.strftime("%Y-%m-%d %H:%M") if dt else "Unknown date"
        sentiment = _sentiment_label(a["votes"])
        votes = a["votes"]
        line = (
            f"### {a['title']}\n"
            f"Source: {a['source']} | Date: {date_str} | Sentiment: {sentiment} "
            f"(+{votes.get('positive',0)}/-{votes.get('negative',0)}, "
            f"important: {votes.get('important',0)})\n"
        )
        if a["url"]:
            line += f"URL: {a['url']}\n"
        lines.append(line)

    return lines


def get_crypto_news_cryptopanic(
    ticker: Annotated[str, "Crypto ticker, e.g. BTC/USDT or BTC"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch asset-specific crypto news from CryptoPanic with sentiment scores."""
    currency = _parse_currency(ticker)
    params = {
        "auth_token": _get_api_key(),
        "currencies": currency,
        "kind": "news",
        "public": "true",
    }

    articles = _fetch_posts(params, start_date)
    lines = _format_articles(articles, start_date, end_date)

    if not lines:
        return f"No CryptoPanic news found for {currency} between {start_date} and {end_date}"

    header = (
        f"## {currency} News from CryptoPanic ({start_date} to {end_date})\n"
        f"Total articles: {len(lines)}\n\n"
    )
    return header + "\n".join(lines)


def get_global_crypto_news_cryptopanic(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 20,
) -> str:
    """Fetch broad crypto market news from CryptoPanic (no asset filter)."""
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_date = (curr_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    params = {
        "auth_token": _get_api_key(),
        "kind": "news",
        "filter": "hot",
        "public": "true",
    }

    articles = _fetch_posts(params, start_date)
    lines = _format_articles(articles, start_date, curr_date)[:limit]

    if not lines:
        return f"No global crypto news found between {start_date} and {curr_date}"

    header = (
        f"## Global Crypto Market News from CryptoPanic ({start_date} to {curr_date})\n"
        f"Total articles: {len(lines)}\n\n"
    )
    return header + "\n".join(lines)
