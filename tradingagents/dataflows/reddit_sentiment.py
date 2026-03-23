"""Reddit-based social sentiment for crypto assets.

Uses Reddit's public JSON API — no API key required.
"""

import requests
from datetime import datetime, timedelta
from typing import Annotated

HEADERS = {"User-Agent": "TradingAgents/1.0"}

# Map base currencies to their most relevant subreddits
ASSET_SUBREDDITS = {
    "BTC":  ["Bitcoin", "CryptoCurrency"],
    "ETH":  ["ethereum", "CryptoCurrency"],
    "SOL":  ["solana", "CryptoCurrency"],
    "BNB":  ["binance", "CryptoCurrency"],
    "XRP":  ["Ripple", "CryptoCurrency"],
    "ADA":  ["cardano", "CryptoCurrency"],
    "DOGE": ["dogecoin", "CryptoCurrency"],
    "AVAX": ["Avax", "CryptoCurrency"],
    "DOT":  ["dot", "CryptoCurrency"],
    "LINK": ["Chainlink", "CryptoCurrency"],
}
DEFAULT_SUBREDDITS = ["CryptoCurrency", "CryptoMarkets"]
GLOBAL_SUBREDDITS  = ["CryptoCurrency", "CryptoMarkets"]


def _parse_currency(ticker: str) -> str:
    for sep in ["/", "-", "_"]:
        if sep in ticker:
            return ticker.split(sep)[0].upper()
    return ticker.upper()


def _sentiment_from_ratio(ratio: float) -> str:
    if ratio >= 0.85:
        return "Very Bullish"
    elif ratio >= 0.70:
        return "Bullish"
    elif ratio >= 0.55:
        return "Neutral"
    elif ratio >= 0.40:
        return "Bearish"
    return "Very Bearish"


def _search_subreddit(subreddit: str, query: str, time_filter: str = "week", limit: int = 25) -> list:
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "sort": "top", "t": time_filter, "limit": limit, "restrict_sr": 1}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("children", [])
    except Exception:
        return []


def _fetch_hot(subreddit: str, limit: int = 25) -> list:
    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
    try:
        resp = requests.get(url, headers=HEADERS, params={"limit": limit}, timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("children", [])
    except Exception:
        return []


def _format_post(post: dict, rank: int) -> str:
    d = post.get("data", {})
    title        = d.get("title", "")
    score        = d.get("score", 0)
    ratio        = d.get("upvote_ratio", 0.5)
    comments     = d.get("num_comments", 0)
    subreddit    = d.get("subreddit", "")
    created_utc  = d.get("created_utc", 0)
    created_str  = datetime.utcfromtimestamp(created_utc).strftime("%Y-%m-%d %H:%M") if created_utc else "Unknown"
    sentiment    = _sentiment_from_ratio(ratio)
    selftext     = d.get("selftext", "")[:300].replace("\n", " ").strip()

    lines = [
        f"**#{rank}** [{subreddit}] {title}",
        f"Score: {score} | Upvote ratio: {ratio:.0%} | Comments: {comments} | Sentiment: {sentiment} | Date: {created_str}",
    ]
    if selftext:
        lines.append(f"Preview: {selftext}...")
    return "\n".join(lines)


def get_reddit_sentiment(
    ticker: Annotated[str, "Crypto ticker, e.g. BTC/USDT or BTC"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch Reddit posts for a crypto asset and return engagement + sentiment metrics."""
    currency = _parse_currency(ticker)
    subreddits = ASSET_SUBREDDITS.get(currency, DEFAULT_SUBREDDITS)

    # Pick Reddit time filter that covers the requested range
    days = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days
    time_filter = "day" if days <= 1 else "week" if days <= 7 else "month"

    all_posts = []
    seen = set()
    for sub in subreddits:
        for post in _search_subreddit(sub, currency, time_filter):
            pid = post.get("data", {}).get("id")
            if pid and pid not in seen:
                seen.add(pid)
                all_posts.append(post)

    if not all_posts:
        return f"No Reddit posts found for {currency} between {start_date} and {end_date}"

    # Sort by score desc
    all_posts.sort(key=lambda p: p.get("data", {}).get("score", 0), reverse=True)
    top_posts = all_posts[:20]

    # Aggregate sentiment
    ratios = [p.get("data", {}).get("upvote_ratio", 0.5) for p in top_posts]
    avg_ratio = sum(ratios) / len(ratios)
    total_score = sum(p.get("data", {}).get("score", 0) for p in top_posts)
    total_comments = sum(p.get("data", {}).get("num_comments", 0) for p in top_posts)
    bullish = sum(1 for r in ratios if r >= 0.70)
    bearish = sum(1 for r in ratios if r < 0.50)

    summary = (
        f"## Reddit Sentiment for {currency} ({start_date} to {end_date})\n\n"
        f"**Aggregate (top {len(top_posts)} posts)**\n"
        f"- Avg upvote ratio: {avg_ratio:.0%} → {_sentiment_from_ratio(avg_ratio)}\n"
        f"- Bullish posts: {bullish} | Bearish posts: {bearish} | Neutral: {len(top_posts) - bullish - bearish}\n"
        f"- Total engagement: {total_score:,} upvotes, {total_comments:,} comments\n\n"
        f"**Top Posts**\n\n"
    )
    post_lines = "\n\n".join(_format_post(p, i + 1) for i, p in enumerate(top_posts[:10]))
    return summary + post_lines


def get_global_reddit_sentiment(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of posts to return"] = 20,
) -> str:
    """Fetch hot posts from major crypto subreddits for broad market sentiment."""
    start_date = (datetime.strptime(curr_date, "%Y-%m-%d") - timedelta(days=look_back_days)).strftime("%Y-%m-%d")

    all_posts = []
    seen = set()
    for sub in GLOBAL_SUBREDDITS:
        for post in _fetch_hot(sub, limit=25):
            pid = post.get("data", {}).get("id")
            if pid and pid not in seen:
                seen.add(pid)
                all_posts.append(post)

    if not all_posts:
        return f"No Reddit posts found for global crypto market around {curr_date}"

    all_posts.sort(key=lambda p: p.get("data", {}).get("score", 0), reverse=True)
    top_posts = all_posts[:limit]

    ratios = [p.get("data", {}).get("upvote_ratio", 0.5) for p in top_posts]
    avg_ratio = sum(ratios) / len(ratios)
    bullish = sum(1 for r in ratios if r >= 0.70)
    bearish = sum(1 for r in ratios if r < 0.50)

    summary = (
        f"## Global Crypto Reddit Sentiment ({start_date} to {curr_date})\n\n"
        f"**Aggregate (top {len(top_posts)} hot posts)**\n"
        f"- Avg upvote ratio: {avg_ratio:.0%} → {_sentiment_from_ratio(avg_ratio)}\n"
        f"- Bullish posts: {bullish} | Bearish posts: {bearish} | Neutral: {len(top_posts) - bullish - bearish}\n\n"
        f"**Top Posts**\n\n"
    )
    post_lines = "\n\n".join(_format_post(p, i + 1) for i, p in enumerate(top_posts[:limit]))
    return summary + post_lines
