import asyncio
from fastapi import FastAPI, HTTPException
import httpx

# --- 匯入內部資料模型 ---
from models import WatchlistRequest, AnalyzeRequest

# --- 匯入選股雷達模組 ---
from stock_scanner import run_single_scan

# --- 匯入四大面向核心抓取函式 (直接調用回傳 dict 的底層非同步函式) ---
from fundamental_server import fetch_fundamental_data
from chip_server import fetch_tw_chip, fetch_us_chip
from tech_server import fetch_technical_data
from sentiment_server import fetch_sentiment_data

# --- 建立 FastAPI 實例 ---
app = FastAPI(
    title="Stock Command Center API",
    description="結合三重濾網雷達與四大面向深度分析的股票雲端決策中樞",
    version="2.0.0"
)

# ==========================================
# 根目錄健康檢查 (Health Check)
# ==========================================
@app.get("/")
async def root():
    """提供給 Render 或外部保活機制確認伺服器是否正常運行"""
    return {"status": "ok", "message": "Stock Command Center API is running."}


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

    # 限制並發連線數，避免短時間內連線過多遭外部 API Rate Limit
    limits = httpx.Limits(max_connections=15)
    
    try:
        async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
            # 並發分派任務給 stock_scanner
            tasks = [run_single_scan(client, symbol) for symbol in request.symbols]
            results = await asyncio.gather(*tasks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"雷達掃描執行失敗: {str(e)}")

    # 抽取符合三重濾網條件的強勢標的
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
    針對單一標的，並發執行基本面、技術面、籌碼面與消息面的深度資料抓取與評分。
    提供給 70/30 核心衛星策略做最終決策依據。
    """
    if not request.symbol:
        raise HTTPException(status_code=400, detail="必須提供股票代號 (Symbol is required)")

    symbol = request.symbol.upper().strip()
    
    # 判斷是否為台股 (包含純數字、.TW、.TWO)
    is_tw_stock = any(char.isdigit() for char in symbol) or symbol.endswith(".TW") or symbol.endswith(".TWO")

    # 籌碼面依照台股/美股分流至對應函式
    chip_task = fetch_tw_chip(symbol) if is_tw_stock else fetch_us_chip(symbol)

    try:
        # 並發分派任務，各函式均只接收 symbol，不傳遞多餘的 client
        fund, tech, chip, sent = await asyncio.gather(
            fetch_fundamental_data(symbol),
            fetch_technical_data(symbol),
            chip_task,
            fetch_sentiment_data(symbol)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"深度分析執行失敗: {str(e)}")
        
    return {
        "status": "success",
        "symbol": request.symbol,
        "fundamental": fund,
        "technical": tech,
        "chip": chip,
        "sentiment": sent,
        "overall_summary": "綜合四大面向資料抓取完成，請交由 AI 指揮中心判定最終決策。"
    }