import os
import json
import httpx
import asyncio
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ChipAnalyzer")
FINNHUB_API_KEY = "dbibn7hr01qie36m6eggdbibn7hr01qie36m6eh0"

async def fetch_tw_chip(symbol: str) -> dict:
    """直接呼叫 FinMind HTTP API 抓取台股三大法人買賣超"""
    clean_symbol = symbol.replace(".TW", "").replace(".TWO", "")
    
    # 動態抓取近 30 天，確保資料足夠且不會 Timeout
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id={clean_symbol}&start_date={start_date}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            # 這裡就是剛剛不見的 raw_data 定義！
            raw_data = response.json()
        except Exception as e:
            return {"status": "error", "summary": f"FinMind API 請求失敗: {str(e)}"}
            
    if raw_data.get("msg") != "success" or not raw_data.get("data"):
        return {"status": "error", "summary": "查無法人買賣超資料。"}
        
    data = raw_data["data"]
    
    # 🚀 使用英文字串比對，忽略大小寫
    foreign_investor = sum(
        int(item.get("buy", 0)) - int(item.get("sell", 0)) 
        for item in data if "foreign" in item.get("name", "").lower()
    )
    investment_trust = sum(
        int(item.get("buy", 0)) - int(item.get("sell", 0)) 
        for item in data if "investment" in item.get("name", "").lower()
    )
    dealer = sum(
        int(item.get("buy", 0)) - int(item.get("sell", 0)) 
        for item in data if "dealer" in item.get("name", "").lower() and "foreign" not in item.get("name", "").lower()
    )
    
    total_net_buy = foreign_investor + investment_trust + dealer
    
    score = 5
    if total_net_buy > 0: score += 2
    if investment_trust > 0: score += 1 
    if total_net_buy < 0: score -= 2
    
    trading_days = len(set(item.get("date") for item in data))
    
    return {
        "agent": "chip",
        "symbol": symbol,
        "status": "success",
        "data": {
            "foreign_net_buy": foreign_investor,
            "trust_net_buy": investment_trust,
            "dealer_net_buy": dealer,
            "total_net_buy": total_net_buy
        },
        "summary": f"統計 {trading_days} 個交易日。三大法人合計買賣超: {total_net_buy:,} 股。",
        "score": score
    }

async def fetch_us_chip(symbol: str) -> dict:
    """使用 Finnhub API 抓取美股內部人情緒"""
    _from = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    _to = datetime.now().strftime("%Y-%m-%d")
    
    url = f"https://finnhub.io/api/v1/stock/insider-sentiment?symbol={symbol}&from={_from}&to={_to}&token={FINNHUB_API_KEY}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            raw_data = response.json()
        except Exception as e:
            return {"status": "error", "summary": f"Finnhub API 請求失敗: {str(e)}"}
            
    if not raw_data.get("data"):
        return {"status": "error", "summary": "查無美股內部人情緒數據。"}
        
    data = raw_data["data"]
    total_mspr = sum(item.get("mspr", 0) for item in data)
    
    score = 5
    if total_mspr > 0: score += 2
    if total_mspr < 0: score -= 2
    
    return {
        "agent": "chip",
        "symbol": symbol,
        "status": "success",
        "data": {
            "insider_sentiment_mspr": round(total_mspr, 4)
        },
        "summary": "美股內部人情緒數據獲取成功 (正值代表內部人偏向買進)。",
        "score": score
    }

@mcp.tool()
async def get_chip_analysis(symbol: str) -> str:
    """獲取股票籌碼面數據 (台股為三大法人買賣超，美股為內部人情緒)。"""
    symbol = symbol.upper().strip()
    is_tw_stock = any(char.isdigit() for char in symbol) or symbol.endswith(".TW") or symbol.endswith(".TWO")
    
    if is_tw_stock:
        report_dict = await fetch_tw_chip(symbol)
    else:
        report_dict = await fetch_us_chip(symbol)
        
    return json.dumps(report_dict, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport='stdio')