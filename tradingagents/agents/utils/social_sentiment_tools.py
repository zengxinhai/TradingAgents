from langchain_core.tools import tool
from typing import Annotated
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_social_sentiment(
    ticker: Annotated[str, "Crypto ticker, e.g. BTC/USDT or BTC"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve social media sentiment for a crypto asset.
    Returns top posts with engagement metrics and aggregated sentiment.
    """
    return route_to_vendor("get_social_sentiment", ticker, start_date, end_date)


@tool
def get_global_social_sentiment(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of posts to return"] = 20,
) -> str:
    """
    Retrieve broad crypto market social sentiment from major community forums.
    Returns trending posts with engagement metrics and aggregated sentiment.
    """
    return route_to_vendor("get_global_social_sentiment", curr_date, look_back_days, limit)
