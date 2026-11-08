from pydantic import BaseModel, Field
from typing import List

class WatchlistRequest(BaseModel):
    """
    對應 /api/scan 路由的請求格式
    用於接收一整包準備進行三重濾網快篩的股票代號清單
    """
    symbols: List[str] = Field(
        ..., 
        description="股票代號清單，例如：[\"2330\", \"2317\", \"2454\"]",
        example=["2330", "2317", "2454"]
    )


class AnalyzeRequest(BaseModel):
    """
    對應 /api/analyze 路由的請求格式
    用於接收單一準備進行四大面向深度分析的股票代號
    """
    symbol: str = Field(
        ..., 
        description="單一股票代號，例如：\"2330\"",
        example="2330"
    )