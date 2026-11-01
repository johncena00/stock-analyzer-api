import time
from FinMind.data import DataLoader

print("開始向 FinMind 發送請求...")
start_time = time.time()

try:
    api = DataLoader()
    # 只抓近幾天的資料
    df = api.taiwan_stock_institutional_investors_buy_sell(
        stock_id="2330", 
        start_date="2026-10-01"
    )
    print(df.head())
    print(f"✅ 成功！耗時: {time.time() - start_time:.2f} 秒")
except Exception as e:
    print(f"❌ 發生錯誤: {e}")