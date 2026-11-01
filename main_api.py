from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
import asyncio

# 引入你原本寫好的四個分析核心邏輯函數
# (假設已將 fundamental, chip, tech, sentiment 模組化)
from fundamental_server import fetch_fundamental_data
from chip_server import fetch_chip_data
from tech_server import fetch_technical_data
from sentiment_server import fetch_sentiment_data

app = FastAPI(title="Stock Analyzer Cloud Gateway", version="1.0")

class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    symbol: str

@app.post("/api/analyze")
async def analyze_stock(req: AnalyzeRequest):
    symbol = req.symbol.upper().strip()
    
    # 並行調四大面向分析
    fund_res, chip_res, tech_res, sent_res = await asyncio.gather(
        fetch_fundamental_data(symbol),
        fetch_chip_data(symbol),
        fetch_technical_data(symbol),
        fetch_sentiment_data(symbol),
        return_exceptions=True
    )
    
    return {
        "symbol": symbol,
        "fundamental": fund_res if not isinstance(fund_res, Exception) else {"status": "error"},
        "chip": chip_res if not isinstance(chip_res, Exception) else {"status": "error"},
        "technical": tech_res if not isinstance(tech_res, Exception) else {"status": "error"},
        "sentiment": sent_res if not isinstance(sent_res, Exception) else {"status": "error"}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)