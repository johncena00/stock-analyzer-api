import json
import asyncio
from mcp.server.fastmcp import FastMCP
import yfinance as yf
import pandas as pd

mcp = FastMCP("TechAnalyzer")

async def fetch_technical_data(symbol: str) -> dict:
    """使用 yfinance 抓取歷史股價並計算技術指標 (MA, RSI) - 具備防呆機制"""
    clean_symbol = symbol.upper().strip()
    
    # 智慧補齊台股後綴
    if clean_symbol.isdigit() and len(clean_symbol) == 4:
        clean_symbol = f"{clean_symbol}.TW"
    
    def _fetch():
        ticker = yf.Ticker(clean_symbol)
        df = ticker.history(period="1y")
        return df

    try:
        df = await asyncio.to_thread(_fetch)
    except Exception as e:
        return {"status": "error", "summary": f"股價歷史資料抓取失敗: {str(e)}"}

    if df is None or df.empty:
        if clean_symbol.endswith(".TW"):
            alt_symbol = clean_symbol.replace(".TW", ".TWO")
            try:
                ticker = yf.Ticker(alt_symbol)
                df = await asyncio.to_thread(ticker.history, period="1y")
            except Exception:
                pass
                
    if df is None or df.empty or len(df) < 5:
        return {"status": "error", "summary": f"查無代號 {symbol} 的足夠歷史股價資料（交易日少於 5 天）。"}

    # 取得收盤價 Series
    close_prices = df['Close']
    current_price = float(close_prices.iloc[-1])
    
    # 安全計算均線（若資料不足 60/20 天則自動放寬或回傳 None）
    def safe_mean(series, window):
        if len(series) >= window:
            val = series.rolling(window=window).mean().iloc[-1]
            return float(val) if pd.notna(val) else None
        return None

    ma5 = safe_mean(close_prices, 5)
    ma20 = safe_mean(close_prices, 20)
    ma60 = safe_mean(close_prices, 60)
    
    # 安全計算 RSI (14)
    rsi = 50.0 # 預設中性值
    if len(close_prices) >= 15:
        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        val = rsi_series.iloc[-1]
        if pd.notna(val):
            rsi = float(val)

    # 智慧趨勢判定與評分邏輯
    score = 5
    trend_status = "盤整震盪"
    
    if ma20 is not None and current_price > ma20 and (ma5 is None or ma5 > ma20):
        trend_status = "多頭排列 (短多強勢)"
        score += 2
    elif ma20 is not None and current_price < ma20 and (ma5 is None or ma5 < ma20):
        trend_status = "空頭排列 (短空弱勢)"
        score -= 2
        
    if rsi > 70:
        trend_status += " [RSI過熱警示]"
        score -= 1
    elif rsi < 30:
        trend_status += " [RSI超賣築底]"
        score += 1

    return {
        "agent": "technical",
        "symbol": symbol,
        "status": "success",
        "data": {
            "current_price": round(current_price, 2),
            "MA5": round(ma5, 2) if ma5 is not None else None,
            "MA20": round(ma20, 2) if ma20 is not None else None,
            "MA60": round(ma60, 2) if ma60 is not None else None,
            "RSI_14": round(rsi, 2),
            "trend": trend_status
        },
        "summary": f"現價 {current_price:.2f}。技術趨勢：{trend_status}，RSI(14)：{rsi:.2f}。",
        "score": max(1, min(10, score))
    }

@mcp.tool()
async def get_technical_analysis(symbol: str) -> str:
    """獲取股票技術面分析數據 (包含均線 MA5/20/60、RSI 與多空趨勢判定)。"""
    result = await fetch_technical_data(symbol)
    return json.dumps(result, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport='stdio')