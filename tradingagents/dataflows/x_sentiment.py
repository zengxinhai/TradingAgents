"""X (Twitter) social sentiment for crypto assets via tweepy v2 API.

Requires X API v2 Bearer Token (Basic tier, $100/month).
Set X_BEARER_TOKEN environment variable.

Note: search_recent_tweets covers the last 7 days only on Basic tier.
Full-archive search requires the Pro tier ($5,000/month).
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated


# Cashtag + keyword queries per asset
ASSET_QUERIES = {
    "BTC":  '($BTC OR #Bitcoin OR "bitcoin") lang:en -is:retweet',
    "ETH":  '($ETH OR #Ethereum OR "ethereum") lang:en -is:retweet',
    "SOL":  '($SOL OR #Solana OR "solana") lang:en -is:retweet',
    "BNB":  '($BNB OR "binance coin") lang:en -is:retweet',
    "XRP":  '($XRP OR #Ripple OR "ripple") lang:en -is:retweet',
    "ADA":  '($ADA OR #Cardano OR "cardano") lang:en -is:retweet',
    "DOGE": '($DOGE OR #Dogecoin OR "dogecoin") lang:en -is:retweet',
    "AVAX": '($AVAX OR #Avalanche OR "avalanche") lang:en -is:retweet',
    "DOT":  '($DOT OR #Polkadot OR "polkadot") lang:en -is:retweet',
    "LINK": '($LINK OR #Chainlink OR "chainlink") lang:en -is:retweet',
}

GLOBAL_QUERY = (
    '(#crypto OR #cryptocurrency OR #Bitcoin OR #DeFi OR $BTC OR $ETH) '
    'lang:en -is:retweet'
)

TWEET_FIELDS  = ["created_at", "public_metrics", "text"]
MAX_RESULTS   = 100  # per request; Basic tier max


def _get_client():
    try:
        import tweepy
    except ImportError:
        raise ImportError("tweepy is required: pip install tweepy")

    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token:
        raise ValueError("X_BEARER_TOKEN environment variable is not set.")

    return tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)


def _parse_currency(ticker: str) -> str:
    for sep in ["/", "-", "_"]:
        if sep in ticker:
            return ticker.split(sep)[0].upper()
    return ticker.upper()


def _to_utc(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _engagement_score(metrics: dict) -> int:
    return (
        metrics.get("like_count", 0)
        + metrics.get("retweet_count", 0) * 3   # retweets weighted higher
        + metrics.get("reply_count", 0)
        + metrics.get("quote_count", 0) * 2
    )


def _format_tweet(tweet, rank: int) -> str:
    m = tweet.public_metrics or {}
    dt = tweet.created_at.strftime("%Y-%m-%d %H:%M") if tweet.created_at else "Unknown"
    text = (tweet.text or "").replace("\n", " ").strip()
    return (
        f"**#{rank}** [{dt}]\n"
        f"{text}\n"
        f"Likes: {m.get('like_count',0):,} | "
        f"Retweets: {m.get('retweet_count',0):,} | "
        f"Replies: {m.get('reply_count',0):,} | "
        f"Quotes: {m.get('quote_count',0):,}"
    )


def _warn_if_beyond_7_days(start_date: str) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    start_dt = _to_utc(start_date)
    if start_dt < cutoff:
        return (
            f"\n> **Note:** X Basic API only covers the last 7 days. "
            f"Requested start {start_date} is beyond that window — "
            f"results shown from {cutoff.strftime('%Y-%m-%d')} onwards.\n"
        )
    return ""


def _search(client, query: str, start_time: datetime, end_time: datetime, limit: int) -> list:
    """Fetch tweets, paginating until limit or no more pages."""
    import tweepy

    tweets = []
    # Clamp start_time to 7-day window for Basic tier
    cutoff = datetime.now(timezone.utc) - timedelta(days=6, hours=23)
    if start_time < cutoff:
        start_time = cutoff

    try:
        paginator = tweepy.Paginator(
            client.search_recent_tweets,
            query=query,
            start_time=start_time,
            end_time=end_time,
            tweet_fields=TWEET_FIELDS,
            max_results=min(MAX_RESULTS, limit),
        )
        for tweet in paginator.flatten(limit=limit):
            tweets.append(tweet)
    except Exception as e:
        raise RuntimeError(f"X API error: {e}")

    return tweets


def get_x_sentiment(
    ticker: Annotated[str, "Crypto ticker, e.g. BTC/USDT or BTC"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Fetch recent X (Twitter) posts for a crypto asset.
    Returns top tweets by engagement so the analyst can assess community sentiment.
    Requires X_BEARER_TOKEN env var.
    """
    currency = _parse_currency(ticker)
    query = ASSET_QUERIES.get(currency, f'(${currency} OR "{currency.lower()}") lang:en -is:retweet')
    warning = _warn_if_beyond_7_days(start_date)

    client = _get_client()
    tweets = _search(client, query, _to_utc(start_date), _to_utc(end_date), limit=100)

    if not tweets:
        return f"No X posts found for {currency} between {start_date} and {end_date}"

    tweets.sort(key=lambda t: _engagement_score(t.public_metrics or {}), reverse=True)
    top = tweets[:20]

    total_likes    = sum(t.public_metrics.get("like_count", 0) for t in tweets if t.public_metrics)
    total_retweets = sum(t.public_metrics.get("retweet_count", 0) for t in tweets if t.public_metrics)
    total_replies  = sum(t.public_metrics.get("reply_count", 0) for t in tweets if t.public_metrics)

    header = (
        f"## X Sentiment for {currency} ({start_date} to {end_date})\n"
        f"{warning}"
        f"**Volume:** {len(tweets)} posts retrieved\n"
        f"**Aggregate engagement:** {total_likes:,} likes | {total_retweets:,} retweets | {total_replies:,} replies\n\n"
        f"**Top posts by engagement:**\n\n"
    )
    body = "\n\n".join(_format_tweet(t, i + 1) for i, t in enumerate(top))
    return header + body


def get_global_x_sentiment(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back (max 7 on Basic tier)"] = 7,
    limit: Annotated[int, "Maximum number of posts to return"] = 30,
) -> str:
    """
    Fetch trending crypto posts from X for broad market sentiment.
    Requires X_BEARER_TOKEN env var.
    """
    end_dt   = _to_utc(curr_date) + timedelta(days=1)
    start_dt = _to_utc(curr_date) - timedelta(days=look_back_days)
    start_date = start_dt.strftime("%Y-%m-%d")

    warning = _warn_if_beyond_7_days(start_date)
    client = _get_client()
    tweets = _search(client, GLOBAL_QUERY, start_dt, end_dt, limit=limit)

    if not tweets:
        return f"No global crypto X posts found around {curr_date}"

    tweets.sort(key=lambda t: _engagement_score(t.public_metrics or {}), reverse=True)
    top = tweets[:limit]

    total_likes    = sum(t.public_metrics.get("like_count", 0) for t in tweets if t.public_metrics)
    total_retweets = sum(t.public_metrics.get("retweet_count", 0) for t in tweets if t.public_metrics)

    header = (
        f"## Global Crypto X Sentiment ({start_date} to {curr_date})\n"
        f"{warning}"
        f"**Volume:** {len(tweets)} posts retrieved\n"
        f"**Aggregate engagement:** {total_likes:,} likes | {total_retweets:,} retweets\n\n"
        f"**Top posts by engagement:**\n\n"
    )
    body = "\n\n".join(_format_tweet(t, i + 1) for i, t in enumerate(top))
    return header + body
