import asyncio
import httpx
import pandas as pd
from datetime import datetime, timedelta

# Finnhub API 金鑰
FINNHUB_API_KEY = "dbibn7hr01qie36m6eggdbibn7hr01qie36m6eh0"

# ==========================================
# 條件一：月營收年增率 (台股保留 FinMind 確保資料完整)
# ==========================================
async def check_revenue_growth(client: httpx.AsyncClient, symbol: str) -> bool:
    clean_symbol = symbol.replace(".TW", "").replace(".TWO", "").strip()
    start_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
    
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockMonthRevenue",
        "data_id": clean_symbol,
        "start_date": start_date
    }
    
    try:
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        records = data.get("data", [])
        if not records:
            return False
            
        df = pd.DataFrame(records)
        if len(df) >= 3:
            yoy_col = next((c for c in ["revenue_year_on_year_ratio", "revenue_YearOnYear_ratio"] if c in df.columns), None)
            if not yoy_col:
                return False
                
            latest_3 = df.tail(3)
            ratios = pd.to_numeric(latest_3[yoy_col], errors='coerce')
            return bool((ratios > 0).all())
        return False
    except Exception:
        return False


# ==========================================
# 條件二：股價站上季線 (全面使用 Finnhub /stock/candle)
# ==========================================
async def check_technical_ma60_finnhub(client: httpx.AsyncClient, symbol: str) -> bool:
    """使用 Finnhub 抓取近 120 天日 K 線，計算 60MA"""
    clean_symbol = symbol.upper().strip()
    
    # 判斷台股標的格式補齊 .TW
    if clean_symbol.isdigit() and len(clean_symbol) == 4:
        clean_symbol = f"{clean_symbol}.TW"
        
    _to = int(datetime.now().timestamp())
    _from = int((datetime.now() - timedelta(days=150)).timestamp())
    
    url = "https://finnhub.io/api/v1/stock/candle"
    params = {
        "symbol": clean_symbol,
        "resolution": "D",
        "from": _from,
        "to": _to,
        "token": FINNHUB_API_KEY
    }
    
    try:
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        # Finnhub 成功時 "s" 欄位會為 "ok"，"c" 為收盤價列表 (Close)
        if data.get("s") != "ok" or not data.get("c"):
            # 若為台股且查無資料，嘗試切換上櫃代號 .TWO
            if clean_symbol.endswith(".TW"):
                params["symbol"] = clean_symbol.replace(".TW", ".TWO")
                resp_alt = await client.get(url, params=params, timeout=10.0)
                data = resp_alt.json()
                if data.get("s") != "ok" or not data.get("c"):
                    return False
            else:
                return False
                
        close_prices = data.get("c", [])
        if len(close_prices) < 60:
            return False
            
        series = pd.Series(close_prices)
        ma_60 = series.rolling(window=60).mean().iloc[-1]
        latest_close = series.iloc[-1]
        
        return bool(latest_close > ma_60)
    except Exception:
        return False


# ==========================================
# 條件三：外資近五日淨買超 (FinMind)
# ==========================================
async def check_foreign_investor_buy(client: httpx.AsyncClient, symbol: str) -> bool:
    clean_symbol = symbol.replace(".TW", "").replace(".TWO", "").strip()
    start_date = (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d")
    
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": clean_symbol,
        "start_date": start_date
    }
    
    try:
        response = await client.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        records = data.get("data", [])
        if not records:
            return False
            
        df = pd.DataFrame(records)
        if df.empty or 'name' not in df.columns:
            return False
        
        is_foreign = df['name'].astype(str).str.contains('外資|foreign', case=False, na=False)
        df_foreign = df[is_foreign]
        if df_foreign.empty:
            return False
            
        df_foreign['buy'] = pd.to_numeric(df_foreign['buy'], errors='coerce').fillna(0)
        df_foreign['sell'] = pd.to_numeric(df_foreign['sell'], errors='coerce').fillna(0)
        
        df_grouped = df_foreign.groupby('date')[['buy', 'sell']].sum().reset_index()
        df_grouped = df_grouped.sort_values('date', ascending=False).head(5)
        
        net_buy = (df_grouped['buy'] - df_grouped['sell']).sum()
        return bool(net_buy > 0)
    except Exception:
        return False


# ==========================================
# 單一標的快篩整合函式
# ==========================================
async def run_single_scan(client: httpx.AsyncClient, symbol: str) -> dict:
    revenue_task = check_revenue_growth(client, symbol)
    tech_task = check_technical_ma60_finnhub(client, symbol)
    chip_task = check_foreign_investor_buy(client, symbol)
    
    rev_pass, tech_pass, chip_pass = await asyncio.gather(
        revenue_task, tech_task, chip_task, return_exceptions=True
    )
    
    rev_result = bool(rev_pass) if isinstance(rev_pass, bool) else False
    tech_result = bool(tech_pass) if isinstance(tech_pass, bool) else False
    chip_result = bool(chip_pass) if isinstance(chip_pass, bool) else False
    
    return {
        "symbol": symbol,
        "revenue_pass": rev_result,
        "tech_pass": tech_result,
        "chip_pass": chip_result,
        "is_target": rev_result and tech_result and chip_result
    }