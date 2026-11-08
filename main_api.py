from fastapi import FastAPI, HTTPException
import httpx
import asyncio

# --- 匯入內部模組 ---
# 從 models.py 匯入資料驗證模型
from models import WatchlistRequest, AnalyzeRequest

# 從 scanner.py 匯入選股雷達邏輯
from stock_scanner import run_single_scan

from fundamental_server import analyze_fundamental
from chip_server import analyze_chip
from tech_server import analyze_technical
from sentiment_server import analyze_sentiment

# --- 建立 FastAPI 實例 ---
app = FastAPI(
    title="Stock Command Center API",
    description="結合三重濾網雷達與四大面向深度分析的股票雲端決策中樞",
    version="2.0.0"
)

# ==========================================
# 路由端點 1：前置雷達 (快篩)
# ==========================================
@app.post("/api/scan", summary="三重濾網選股雷達")
async def scan_stocks(request: WatchlistRequest):
    """
    接收多檔股票代號 (Watchlist)，在雲端並發執行「營收、季線、外資」三重濾網。
    快速刷掉弱勢股，回傳值得深究的強勢名單。
    """
    if not request.symbols:
        raise HTTPException(status_code=400, detail="觀察清單不可為空 (Symbols list cannot be empty)")

    # 限制並發連線數，避免瞬間發送過多請求被外部 API 封鎖
    limits = httpx.Limits(max_connections=15)
    
    # 在最外層建立 HTTP Client，傳遞給底層模組共用
    async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
        # 並發分派任務給 scanner.py
        tasks = [run_single_scan(client, symbol) for symbol in request.symbols]
        results = await asyncio.gather(*tasks)

    # 抽取符合三重濾網的強勢標的
    recommended_targets = [res["symbol"] for res in results if res.get("is_target")]

    return {
        "status": "success",
        "scanned_count": len(request.symbols),
        "recommended_targets": recommended_targets,
        "details": results
    }

# ==========================================
# 路由端點 2：深度分析 (四大面向)
# ==========================================
@app.post("/api/analyze", summary="單檔深度四大面向分析")
async def analyze_stock(request: AnalyzeRequest):
    """
    針對單一標的，並發執行基本面、籌碼面、技術面與消息面的深度資料抓取與評分。
    提供給 70/30 核心衛星策略做最終決策依據。
    """
    if not request.symbol:
        raise HTTPException(status_code=400, detail="必須提供股票代號 (Symbol is required)")

    # 深度分析較耗時，給予較長的 Timeout
    async with httpx.AsyncClient(timeout=45.0) as client:
        # 並發分派任務給 analyzer.py 的四大模組
        fund, tech, chip, sent = await asyncio.gather(
            analyze_fundamental(client, request.symbol),
            analyze_technical(client, request.symbol),
            analyze_chip(client, request.symbol),
            analyze_sentiment(client, request.symbol)
        )
        
    return {
        "status": "success",
        "symbol": request.symbol,
        "fundamental": fund,
        "technical": tech,
        "chip": chip,
        "sentiment": sent,
        "overall_summary": "綜合四大面向資料抓取完成，請交由 AI 指揮中心判定最終決策。"
    }

# ==========================================
# 根目錄健康檢查 (Health Check)
# ==========================================
@app.get("/")
async def root():
    """提供給 Render 或外部服務確認伺服器是否存活 (甦醒)"""
    return {"message": "Stock Command Center API is running."}