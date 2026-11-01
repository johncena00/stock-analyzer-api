import json
import asyncio
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
import httpx

mcp = FastMCP("SentimentAnalyzer")
FINNHUB_API_KEY = "dbibn7hr01qie36m6eggdbibn7hr01qie36m6eh0"

async def fetch_sentiment_data(symbol: str) -> dict:
    """使用 Finnhub 抓取公司新聞與市場情緒數據 (具備美台股智慧切換與 403 防禦)"""
    clean_symbol = symbol.upper().strip()
    
    # 判斷是否為台股代號（包含 .TW, .TWO 或純 4 位數字）
    is_taiwan_stock = clean_symbol.endswith(".TW") or clean_symbol.endswith(".TWO") or (clean_symbol.isdigit() and len(clean_symbol) == 4)
    
    if is_taiwan_stock:
        # 台股直接走防禦性回傳，避免 Finnhub 免費版 403 阻擋
        return {
            "agent": "sentiment",
            "symbol": symbol,
            "status": "success",
            "data": {
                "recent_news_count": 0,
                "positive_headlines": 0,
                "negative_headlines": 0,
                "outlook": "台股標的 (Finnhub API 不支援台股新聞，採中性略過)"
            },
            "summary": "台股標的暫不支援海外新聞情緒 API，維持中性防禦評估。",
            "score": 5
        }
    
    # 美股走正常 Finnhub API 流程
    _from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    _to = datetime.now().strftime("%Y-%m-%d")
    
    url = f"https://finnhub.io/api/v1/company-news?symbol={clean_symbol}&from={_from}&to={_to}&token={FINNHUB_API_KEY}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 403:
                return {
                    "agent": "sentiment",
                    "symbol": symbol,
                    "status": "success",
                    "data": {
                        "recent_news_count": 0,
                        "positive_headlines": 0,
                        "negative_headlines": 0,
                        "outlook": "API 權限受限 (403)"
                    },
                    "summary": "新聞 API 權限受限，採中性評估。",
                    "score": 5
                }
            response.raise_for_status()
            news_list = response.json()
        except Exception as e:
            return {
                "agent": "sentiment",
                "symbol": symbol,
                "status": "success",
                "summary": f"新聞 API 請求略過: {str(e)}",
                "score": 5
            }
            
    if not news_list or not isinstance(news_list, list):
        return {
            "agent": "sentiment",
            "symbol": symbol,
            "status": "success",
            "data": {
                "recent_news_count": 0,
                "positive_headlines": 0,
                "negative_headlines": 0,
                "outlook": "近期無重大新聞事件 (中性)"
            },
            "summary": "查無近期關鍵新聞，市場情緒維持中性平穩。",
            "score": 5
        }
        
    # 關鍵字情緒分析模型
    positive_keywords = ["growth", "beat", "surge", "high", "upgrade", "buy", "outperform", "profit", "expansion"]
    negative_keywords = ["drop", "fall", "miss", "downgrade", "cut", "risk", "lawsuit", "investigation", "loss"]
    
    pos_count = 0
    neg_count = 0
    
    recent_news = news_list[:10]
    for item in recent_news:
        headline = item.get("headline", "").lower()
        if any(k in headline for k in positive_keywords):
            pos_count += 1
        if any(k in headline for k in negative_keywords):
            neg_count += 1
            
    sentiment_score = 5 + (pos_count - neg_count)
    sentiment_score = max(1, min(10, sentiment_score))
    
    outlook = "中性平穩"
    if pos_count > neg_count:
        outlook = "偏多樂觀 (Positive)"
    elif neg_count > pos_count:
        outlook = "偏空謹慎 (Cautious)"

    return {
        "agent": "sentiment",
        "symbol": symbol,
        "status": "success",
        "data": {
            "recent_news_count": len(news_list),
            "positive_headlines": pos_count,
            "negative_headlines": neg_count,
            "outlook": outlook
        },
        "summary": f"分析近期 {len(news_list)} 則美股新聞。情緒傾向：{outlook} (利多 {pos_count} 則 / 利空 {neg_count} 則)。",
        "score": sentiment_score
    }

@mcp.tool()
async def get_sentiment_analysis(symbol: str) -> str:
    """獲取股票消息面與新聞情緒分析數據 (具備美台股智慧切換)。"""
    result = await fetch_sentiment_data(symbol)
    return json.dumps(result, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport='stdio')