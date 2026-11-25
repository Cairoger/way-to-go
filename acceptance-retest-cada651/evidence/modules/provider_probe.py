"""Use the configured-in-code public providers, without reading deployment credentials."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from app.finance_money import reference_rate
from app.planning_weather import forecast

async def main():
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    print("day used for forecast",today,flush=True)
    try:
        rate, as_of = await reference_rate("USD","TWD")
        print("USD/TWD", rate, as_of, flush=True)
    except Exception as error:
        print("FX unavailable", type(error).__name__, getattr(error, "detail", ""), flush=True)
    result=await forecast(today,25.03,121.56,"Asia/Taipei")
    print("Open-Meteo",result, flush=True)

asyncio.run(main())
