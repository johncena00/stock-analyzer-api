[cite: 1]import os
import json
import httpx
import asyncio
import yfinance as yf
from mcp.server.fastmcp import FastMCP

# 初始化 FastMCP 伺服器
mcp = FastMCP("FundamentalAnalyzer")

# 你的 Finnhub API Key
FINNHUB_API_KEY = "dbibn7hr01qie36m6eggdbibn7hr01qie36m6eh0"

async def fetch_taiwan_stock(symbol: str) -> dict:
    """使用 yfinance 抓取台股基本面"""
    def _fetch():
        ticker = yf.Ticker(symbol)
        return ticker.info
    
    try:
        info = await asyncio.to_thread(_fetch)
    except Exception as e:
        return {"status": "error", "summary": f"yfinance 請求失敗: {str(e)}"}
        
    pe_ratio = info.get("trailingPE")
    eps = info.get("trailingEps")
    
    roe = info.get("returnOnEquity")
    roe = roe * 100 if roe is not None else None
        
    revenue_growth = info.get("revenueGrowth")
    revenue_growth = revenue_growth * 100 if revenue_growth is not None else None
        
    score = 5
    if roe and roe > 15: score += 2
    if revenue_growth and revenue_growth > 10: score += 1
    if pe_ratio and pe_ratio < 20: score += 1

    return {
        "agent": "fundamental",
        "symbol": symbol,
        "status": "success",
        "data": {
            "PE_ratio": round(pe_ratio, 2) if pe_ratio else None,
            "EPS": round(eps, 2) if eps else None,
            "ROE": round(roe, 2) if roe else None,
            "revenue_growth": round(revenue_growth, 2) if revenue_growth else None
        },
        "summary": "台股數據抓取成功 (來源: yfinance)，等待決策中心綜合評估。",
        "score": score
    }

async def fetch_us_stock(symbol: str) -> dict:
    """使用 Finnhub 抓取美股基本面"""
    url = f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={FINNHUB_API_KEY}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            raw_data = response.json()
        except Exception as e:
            return {"status": "error", "summary": f"Finnhub API 請求失敗: {str(e)}"}
            
    if "metric" not in raw_data or not raw_data["metric"]:
        return {"status": "error", "summary": "查無此股票或無基本面數據"}
        
    metrics = raw_data["metric"]
    pe_ratio = metrics.get("peExclExtraTTM") or metrics.get("peNormalizedAnnual")
    eps = metrics.get("epsExclExtraItemsTTM") or metrics.get("epsNormalizedAnnual")
    roe = metrics.get("roeTTM")
    revenue_growth = metrics.get("revenueGrowthTTMYoy")
    
    score = 5
    if roe and roe > 15: score += 2
    if revenue_growth and revenue_growth > 10: score += 1
    if pe_ratio and pe_ratio < 20: score += 1
    
    return {
        "agent": "fundamental",
        "symbol": symbol,
        "status": "success",
        "data": {
            "PE_ratio": round(pe_ratio, 2) if pe_ratio else None,
            "EPS": round(eps, 2) if eps else None,
            "ROE": round(roe, 2) if roe else None,
            "revenue_growth": round(revenue_growth, 2) if revenue_growth else None
        },
        "summary": "美股數據抓取成功 (來源: Finnhub)，等待決策中心綜合評估。",
        "score": score
    }

async def fetch_fundamental_data(symbol: str) -> dict:
    """
    對外提供給 FastAPI 雲端網關調用的核心封裝函數
    """
    symbol = symbol.upper().strip()
    is_tw_stock = any(char.isdigit() for char in symbol) or symbol.endswith(".TW") or symbol.endswith(".TWO")
    
    if is_tw_stock:
        if symbol.isdigit():
            symbol = f"{symbol}.TW"
        return await fetch_taiwan_stock(symbol)
    else:
        return await fetch_us_stock(symbol)

@mcp.tool()
async def get_fundamental_analysis(symbol: str) -> str:
    """
    獲取股票基本面數據 (包含 P/E、EPS、ROE 等)。
    自動判斷台股與美股並路由至對應的資料源。輸入台股可純打數字 (如 2330)。
    
    Args:
        symbol: 股票代號 (例如: TSM, AAPL, 2330, 0050.TW)
    """
    report_dict = await fetch_fundamental_data(symbol)
    return json.dumps(report_dict, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport='stdio')