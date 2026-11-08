import asyncio
import httpx
import pandas as pd
from datetime import datetime, timedelta

async def check_revenue_growth(client: httpx.AsyncClient, symbol: str) -> bool:
    """條件一：過去一年內，最新連續三個月的「月營收年增率 (YoY)」皆大於 0"""
    start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockMonthRevenue",
        "data_id": symbol,
        "start_date": start_date
    }
    
    try:
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == 200 and data.get("data"):
            df = pd.DataFrame(data["data"])
            if len(df) >= 3:
                latest_3_months = df.tail(3)
                # 檢查這三個月的營收年增率是否都大於 0
                if all(latest_3_months["revenue_YearOnYear_ratio"] > 0):
                    return True
        return False
    except Exception:
        return False

async def check_technical_ma60(symbol: str) -> bool:
    """條件二：目前最新收盤價站上季線 (60MA)"""
    yf_symbol = f"{symbol}.TW"
    
    def _fetch_history():
        import yfinance as yf
        ticker = yf.Ticker(yf_symbol)
        return ticker.history(period="6mo")
    
    try:
        # 使用 to_thread 避免 yfinance 的同步阻塞影響 FastAPI 非同步效能
        hist = await asyncio.to_thread(_fetch_history)
        if len(hist) < 60:
            return False
            
        ma_60 = hist['Close'].rolling(window=60).mean().iloc[-1]
        latest_close = hist['Close'].iloc[-1]
        
        return latest_close > ma_60
    except Exception:
        return False

async def check_foreign_investor_buy(client: httpx.AsyncClient, symbol: str) -> bool:
    """條件三：外資近五日累計買賣超加總大於 0 (淨買超)"""
    start_date = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": symbol,
        "start_date": start_date
    }
    
    try:
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == 200 and data.get("data"):
            df = pd.DataFrame(data["data"])
            if df.empty:
                return False
            
            # 篩選出包含「外資」的欄位
            df_foreign = df[df['name'].str.contains('外資')]
            if df_foreign.empty:
                return False
                
            # 依日期加總買賣超
            df_grouped = df_foreign.groupby('date')[['buy', 'sell']].sum().reset_index()
            df_grouped = df_grouped.sort_values('date', ascending=False).head(5)
            
            # 計算近五日總計：總買進 - 總賣出
            net_buy = (df_grouped['buy'] - df_grouped['sell']).sum()
            
            return net_buy > 0
        return False
    except Exception:
        return False

async def run_single_scan(client: httpx.AsyncClient, symbol: str) -> dict:
    """
    針對單一股票代號，並發執行「營收、季線、外資」三大條件檢查
    回傳該標的的檢核細節與是否達標 (is_target)
    """
    revenue_task = check_revenue_growth(client, symbol)
    tech_task = check_technical_ma60(symbol)
    chip_task = check_foreign_investor_buy(client, symbol)
    
    rev_pass, tech_pass, chip_pass = await asyncio.gather(revenue_task, tech_task, chip_task)
    
    return {
        "symbol": symbol,
        "revenue_pass": rev_pass,
        "tech_pass": tech_pass,
        "chip_pass": chip_pass,
        "is_target": rev_pass and tech_pass and chip_pass
    }