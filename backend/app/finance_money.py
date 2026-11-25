import os
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

import httpx

from .core import fail

# ISO 4217 minor units for currencies with nonstandard decimal precision.
ZERO = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "ISK",
    "JPY",
    "KMF",
    "KRW",
    "PYG",
    "RWF",
    "UGX",
    "UYI",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}
THREE = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}
FOUR = {"CLF", "UYW"}
LIMIT = 10**16


def digits(currency):
    if currency in ZERO:
        return 0
    if currency in THREE:
        return 3
    return 4 if currency in FOUR else 2


def format_money(minor: int, currency: str):
    return format(Decimal(minor).scaleb(-digits(currency)), f".{digits(currency)}f")


def to_minor(value: Decimal, currency: str, *, rounded=False):
    with localcontext() as ctx:
        ctx.prec = 64
        units = value.scaleb(digits(currency))
        integer = units.to_integral_value(rounding=ROUND_HALF_UP)
        if (not rounded and units != integer) or abs(integer) > LIMIT:
            fail(
                422,
                "INVALID_MONEY",
                f"{currency} 金額最多有 {digits(currency)} 位小數，且需在可記錄範圍內。",
            )
        return int(integer)


def allocate(total: int, weights: dict[str, int]):
    denominator = sum(weights.values())
    shares, remainders = {}, []
    for user_id, weight in weights.items():
        shares[user_id], remainder = divmod(total * weight, denominator)
        remainders.append((-remainder, user_id))
    for _, user_id in sorted(remainders)[: total - sum(shares.values())]:
        shares[user_id] += 1
    return shares


def suggested_transfers(balances):
    creditors = sorted([[-n, who] for who, n in balances.items() if n > 0])
    debtors = sorted([[n, who] for who, n in balances.items() if n < 0])
    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(-debtors[i][0], -creditors[j][0])
        transfers.append((debtors[i][1], creditors[j][1], amount))
        debtors[i][0] += amount
        creditors[j][0] += amount
        i += debtors[i][0] == 0
        j += creditors[j][0] == 0
    return transfers


async def reference_rate(source: str, target: str):
    endpoint = os.getenv("FRANKFURTER_URL", "https://api.frankfurter.dev/v2").rstrip("/")
    if not endpoint:
        fail(503, "RATE_UNAVAILABLE", "此站台已停用參考匯率查詢，請手動填寫。")
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            response = await client.get(f"{endpoint}/rate/{source}/{target}")
            response.raise_for_status()
            item = response.json(parse_float=Decimal)
        rate = Decimal(str(item["rate"]))
        if (
            (item["base"].upper(), item["quote"].upper()) != (source, target)
            or not rate.is_finite()
            or not 0 < rate <= 10**10
        ):
            raise ValueError("unexpected rate")
        rate = rate.quantize(Decimal("0.000000000001"))
        if rate <= 0:
            raise ValueError("rate below precision")
        return format(rate.normalize(), "f"), date.fromisoformat(item["date"])
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, InvalidOperation):
        fail(503, "RATE_UNAVAILABLE", "目前沒有可用的參考匯率，請稍後再試或手動填寫。")
