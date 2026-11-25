import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Annotated, Literal

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import delete, select

from . import finance_money
from .core import DB, Actor, audit, check_version, digest, fail, require_member
from .finance_models import (
    Budget,
    ExchangeRateSnapshot,
    Expense,
    ExpensePayer,
    ExpenseSplit,
    FinanceLedger,
    Settlement,
)
from .finance_money import allocate, format_money, suggested_transfers, to_minor
from .merge_models import GuestMerge
from .models import CreationKey, Membership, User, as_utc, utcnow
from .realtime import hub

router = APIRouter(prefix="/trips/{trip_id}", tags=["預算與分帳"])
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Currency = Annotated[str, StringConstraints(to_upper=True, pattern="^[A-Za-z]{3}$")]
Amount = Annotated[Decimal, Field(gt=0, max_digits=20, decimal_places=4)]
Exchange = Annotated[Decimal, Field(gt=0, le=10**10, max_digits=23, decimal_places=12)]
Weight = Annotated[Decimal, Field(ge=0, max_digits=20, decimal_places=6)]
KeyHeader = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]


class Form(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str | None = Field(default=None, min_length=1, max_length=128)


class RateRequest(Form):
    currency: Currency


class ExpenseInput(Form):
    title: Label
    category: Category
    incurred_on: date
    kind: Literal["actual", "estimate"]
    currency: Currency
    amount: Amount
    rate_id: str | None = None
    manual_rate: Exchange | None = None
    split_mode: Literal["equal", "custom", "ratio"]
    payers: dict[str, Amount] = Field(min_length=1)
    splits: dict[str, Weight] = Field(min_length=1)


class ExpenseEdit(ExpenseInput):
    version: int = Field(ge=1)


class BudgetInput(Form):
    scope: Literal["trip", "personal", "category"]
    category: Category | None = None
    amount: Amount


class BudgetEdit(Form):
    version: int = Field(ge=1)
    amount: Amount


class SettlementInput(Form):
    version: int = Field(ge=0)
    from_user_id: str
    to_user_id: str
    amount: Amount


def get_ledger(db, trip, create=False):
    ledger = db.scalar(select(FinanceLedger).where(FinanceLedger.trip_id == trip.id))
    if not ledger and create:
        ledger = FinanceLedger(trip_id=trip.id, currency=trip.currency, version=0)
        db.add(ledger)
        db.flush()
    return ledger


def people(db, trip_id):
    return {
        user.id: {
            "nickname": user.nickname,
            "active": member.left_at is None,
            "canonical_id": merged_id or user.id,
        }
        for member, user, merged_id in db.execute(
            select(Membership, User, GuestMerge.account_id)
            .join(User, User.id == Membership.user_id)
            .outerjoin(GuestMerge, GuestMerge.guest_id == User.id)
            .where(Membership.trip_id == trip_id)
        )
    }


def item(db, model, trip_id, resource_id):
    row = db.scalar(select(model).where(model.trip_id == trip_id, model.id == resource_id))
    if not row:
        fail(404, "FINANCE_NOT_FOUND", "找不到這筆旅費資料。")
    return row


def history_manager(trip, author_id, members, actor):
    account = members[author_id]["canonical_id"]
    return account == actor or (actor == trip.owner_id and not members[account]["active"])


def require_allowed(allowed):
    if not allowed:
        fail(403, "FINANCE_PERMISSION", "你沒有這筆旅費紀錄的管理權限。")


def replay(db, trip_id, user_id, operation, body, header):
    key = body.request_id or header
    if not key:
        return None, None
    fingerprint = digest(
        trip_id + json.dumps(body.model_dump(mode="json", exclude={"request_id"}), sort_keys=True)
    )
    saved = db.scalar(
        select(CreationKey).where(
            CreationKey.user_id == user_id,
            CreationKey.operation == operation,
            CreationKey.key == key,
        )
    )
    if saved:
        if saved.request_hash != fingerprint:
            fail(409, "IDEMPOTENCY_CONFLICT", "同一請求識別碼已用於不同的旅費內容。")
        return saved.resource_id, None
    return None, CreationKey(
        user_id=user_id, operation=operation, key=key, request_hash=fingerprint
    )


async def finish(db, trip, actor, ledger, row, action, key=None):
    if key:
        key.resource_id = row.id
        db.add(key)
    ledger.version += 1
    audit(db, trip.id, actor.id, row.__tablename__, row.id, action)
    db.commit()
    await hub.publish(trip.id, {"type": "finance"})
    return {"id": row.id}


def rate_data(rate):
    return {
        "id": rate.id,
        "source_currency": rate.source_currency,
        "base_currency": rate.base_currency,
        "rate": rate.rate,
        "provider": rate.provider,
        "rate_date": rate.rate_date,
        "captured_at": as_utc(rate.captured_at),
    }


@router.post("/finance/rates")
async def quote(trip_id: str, payload: RateRequest, db: DB, user: Actor):
    trip = require_member(db, trip_id, user.id)
    ledger = get_ledger(db, trip)
    base = ledger.currency if ledger else trip.currency
    cached = db.scalar(
        select(ExchangeRateSnapshot)
        .where(
            ExchangeRateSnapshot.trip_id == trip.id,
            ExchangeRateSnapshot.source_currency == payload.currency,
            ExchangeRateSnapshot.base_currency == base,
            ExchangeRateSnapshot.provider == "Frankfurter",
            ExchangeRateSnapshot.captured_at > utcnow() - timedelta(hours=6),
        )
        .order_by(ExchangeRateSnapshot.captured_at.desc())
        .limit(1)
    )
    if cached:
        return rate_data(cached)
    db.rollback()  # do not hold an open transaction while waiting for the external service
    if payload.currency == base:
        value, day, provider = "1", utcnow().date(), "identity"
    else:
        value, day = await finance_money.reference_rate(payload.currency, base)
        provider = "Frankfurter"
    trip = require_member(db, trip_id, user.id, lock=True)
    ledger = get_ledger(db, trip)
    if (ledger.currency if ledger else trip.currency) != base:
        fail(409, "BASE_CHANGED", "記帳幣別已更新，請重新取得參考匯率。")
    snapshot = ExchangeRateSnapshot(
        trip_id=trip.id,
        source_currency=payload.currency,
        base_currency=base,
        rate=value,
        provider=provider,
        rate_date=day,
    )
    db.add(snapshot)
    db.commit()
    return rate_data(snapshot)


def select_rate(db, trip, base, payload):
    if payload.rate_id and payload.manual_rate is not None:
        fail(422, "AMBIGUOUS_RATE", "請選擇參考匯率或手動輸入其中一種。")
    if payload.rate_id:
        snapshot = item(db, ExchangeRateSnapshot, trip.id, payload.rate_id)
        if (snapshot.source_currency, snapshot.base_currency) != (payload.currency, base):
            fail(422, "RATE_PAIR_MISMATCH", "選擇的匯率與本筆幣別不符。")
        return snapshot
    if payload.currency == base:
        value, provider = Decimal(1), "identity"
        if payload.manual_rate is not None and payload.manual_rate != 1:
            fail(422, "INVALID_RATE", "相同幣別的匯率須為 1。")
    elif payload.manual_rate is not None:
        value, provider = payload.manual_rate, "manual"
    else:
        fail(422, "RATE_REQUIRED", "請取得參考匯率或手動輸入換算匯率。")
    snapshot = ExchangeRateSnapshot(
        trip_id=trip.id,
        source_currency=payload.currency,
        base_currency=base,
        rate=format(value, "f"),
        provider=provider,
        rate_date=utcnow().date(),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def expense_components(db, expense_id):
    return (
        db.scalars(select(ExpensePayer).where(ExpensePayer.expense_id == expense_id)).all(),
        db.scalars(select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id)).all(),
    )


def write_expense(db, trip, ledger, user, payload, row=None):
    participants = people(db, trip.id)
    previous = expense_components(db, row.id) if row else ([], [])
    if row:
        require_allowed(history_manager(trip, row.created_by, participants, user.id))
    for submitted, records in zip((payload.payers, payload.splits), previous, strict=True):
        allowed = {who for who, member in participants.items() if member["active"]} | {
            r.user_id for r in records
        }
        if not submitted.keys() <= allowed:
            fail(422, "INVALID_PARTICIPANT", "新的付款人與分攤成員必須是目前旅伴。")
    source_total = to_minor(payload.amount, payload.currency)
    payers = {who: to_minor(value, payload.currency) for who, value in payload.payers.items()}
    if sum(payers.values()) != source_total:
        fail(422, "PAYER_TOTAL", "所有付款金額的合計必須等於費用總額。")
    if payload.split_mode == "custom":
        shares = {who: to_minor(value, payload.currency) for who, value in payload.splits.items()}
        if sum(shares.values()) != source_total:
            fail(422, "SPLIT_TOTAL", "自訂分攤的合計必須等於費用總額。")
    else:
        weights = {
            who: 1 if payload.split_mode == "equal" else int(value * 1000000)
            for who, value in payload.splits.items()
        }
        if min(weights.values()) <= 0:
            fail(422, "INVALID_WEIGHT", "分攤比例必須為正數。")
        shares = allocate(source_total, weights)
    snapshot = select_rate(db, trip, ledger.currency, payload)
    with localcontext() as context:
        context.prec = 64
        base_total = to_minor(
            payload.amount * Decimal(snapshot.rate), ledger.currency, rounded=True
        )
    if not row:
        row = Expense(trip_id=trip.id, created_by=user.id)
        db.add(row)
    else:
        row.version += 1
        for model in (ExpensePayer, ExpenseSplit):
            db.execute(delete(model).where(model.expense_id == row.id))
    for field in ("title", "category", "kind", "incurred_on", "currency", "split_mode"):
        setattr(row, field, getattr(payload, field))
    row.rate_id, row.amount_minor, row.base_minor = snapshot.id, source_total, base_total
    db.flush()
    for model, values in ((ExpensePayer, payers), (ExpenseSplit, shares)):
        converted = allocate(base_total, values)
        for who, amount in values.items():
            fields = {"weight": format(payload.splits[who], "f")} if model == ExpenseSplit else {}
            db.add(
                model(
                    expense_id=row.id,
                    user_id=who,
                    amount_minor=amount,
                    base_minor=converted[who],
                    **fields,
                )
            )
    return row


@router.post("/expenses", status_code=201)
async def add_expense(
    trip_id: str, payload: ExpenseInput, db: DB, user: Actor, key: KeyHeader = None
):
    trip = require_member(db, trip_id, user.id, lock=True)
    existing, receipt = replay(db, trip_id, user.id, "expense", payload, key)
    if existing:
        return {"id": existing}
    ledger = get_ledger(db, trip, True)
    row = write_expense(db, trip, ledger, user, payload)
    return await finish(db, trip, user, ledger, row, "create", receipt)


@router.patch("/expenses/{expense_id}")
async def edit_expense(trip_id: str, expense_id: str, payload: ExpenseEdit, db: DB, user: Actor):
    trip = require_member(db, trip_id, user.id, lock=True)
    row = item(db, Expense, trip_id, expense_id)
    check_version(row, payload.version)
    ledger = get_ledger(db, trip)
    write_expense(db, trip, ledger, user, payload, row)
    return await finish(db, trip, user, ledger, row, "update")


@router.delete("/expenses/{expense_id}")
async def delete_expense(trip_id: str, expense_id: str, version: int, db: DB, user: Actor):
    trip = require_member(db, trip_id, user.id, lock=True)
    row = item(db, Expense, trip_id, expense_id)
    require_allowed(history_manager(trip, row.created_by, people(db, trip_id), user.id))
    check_version(row, version)
    db.delete(row)
    return await finish(db, trip, user, get_ledger(db, trip), row, "remove")


def budget_access(trip, scope, target, actor):
    return target == actor if scope == "personal" else trip.owner_id == actor


@router.post("/budgets", status_code=201)
async def add_budget(
    trip_id: str, payload: BudgetInput, db: DB, user: Actor, key: KeyHeader = None
):
    trip = require_member(db, trip_id, user.id, lock=True)
    target = {"trip": "", "personal": user.id, "category": payload.category}[payload.scope]
    if target is None:
        fail(422, "CATEGORY_REQUIRED", "請輸入預算類別。")
    require_allowed(budget_access(trip, payload.scope, target, user.id))
    existing, receipt = replay(db, trip_id, user.id, "budget", payload, key)
    if existing:
        return {"id": existing}
    ledger = get_ledger(db, trip, True)
    if db.scalar(
        select(Budget.id).where(
            Budget.trip_id == trip_id, Budget.scope == payload.scope, Budget.target == target
        )
    ):
        fail(409, "BUDGET_EXISTS", "這個項目已有預算，可在預算清單調整額度。")
    row = Budget(
        trip_id=trip.id,
        scope=payload.scope,
        target=target,
        amount_minor=to_minor(payload.amount, ledger.currency),
    )
    db.add(row)
    db.flush()
    return await finish(db, trip, user, ledger, row, "create", receipt)


@router.patch("/budgets/{budget_id}")
async def edit_budget(trip_id: str, budget_id: str, payload: BudgetEdit, db: DB, user: Actor):
    trip = require_member(db, trip_id, user.id, lock=True)
    row = item(db, Budget, trip_id, budget_id)
    require_allowed(budget_access(trip, row.scope, row.target, user.id))
    check_version(row, payload.version)
    ledger = get_ledger(db, trip)
    row.amount_minor = to_minor(payload.amount, ledger.currency)
    row.version += 1
    return await finish(db, trip, user, ledger, row, "update")


@router.delete("/budgets/{budget_id}")
async def delete_budget(trip_id: str, budget_id: str, version: int, db: DB, user: Actor):
    trip = require_member(db, trip_id, user.id, lock=True)
    row = item(db, Budget, trip_id, budget_id)
    require_allowed(budget_access(trip, row.scope, row.target, user.id))
    check_version(row, version)
    db.delete(row)
    return await finish(db, trip, user, get_ledger(db, trip), row, "remove")


def allocations(db, model, trip_id):
    result = defaultdict(list)
    for row in db.scalars(select(model).join(Expense).where(Expense.trip_id == trip_id)):
        result[row.expense_id].append(row)
    return result


def financial_state(db, trip, actor_id):
    ledger = get_ledger(db, trip)
    base = ledger.currency if ledger else trip.currency
    members = people(db, trip.id)
    balances = dict.fromkeys((m["canonical_id"] for m in members.values()), 0)
    payers, splits = allocations(db, ExpensePayer, trip.id), allocations(db, ExpenseSplit, trip.id)
    costs = defaultdict(int)
    expenses, budgets, settlements = [], [], []
    rows = db.execute(
        select(Expense, ExchangeRateSnapshot)
        .join(ExchangeRateSnapshot)
        .where(Expense.trip_id == trip.id)
        .order_by(Expense.incurred_on.desc(), Expense.created_at.desc())
    )
    for row, rate in rows:
        costs[row.kind, "trip", ""] += row.base_minor
        costs[row.kind, "category", row.category] += row.base_minor
        for share in splits[row.id]:
            account = members[share.user_id]["canonical_id"]
            costs[row.kind, "personal", account] += share.base_minor
            if row.kind == "actual":
                balances[account] -= share.base_minor
        if row.kind == "actual":
            for payer in payers[row.id]:
                balances[members[payer.user_id]["canonical_id"]] += payer.base_minor
        expenses.append(
            {
                "id": row.id,
                "title": row.title,
                "kind": row.kind,
                "category": row.category,
                "incurred_on": row.incurred_on,
                "created_by": row.created_by,
                "version": row.version,
                "editable": history_manager(trip, row.created_by, members, actor_id),
                "amount": format_money(row.amount_minor, row.currency),
                "currency": row.currency,
                "base_amount": format_money(row.base_minor, base),
                "rate": rate_data(rate),
                "split_mode": row.split_mode,
                "payers": {
                    r.user_id: format_money(r.amount_minor, row.currency) for r in payers[row.id]
                },
                "splits": {
                    r.user_id: {
                        "amount": format_money(r.amount_minor, row.currency),
                        "weight": r.weight,
                    }
                    for r in splits[row.id]
                },
            }
        )
    for budget in db.scalars(
        select(Budget).where(Budget.trip_id == trip.id).order_by(Budget.scope, Budget.target)
    ):
        if budget.scope == "personal" and budget.target != actor_id:
            continue
        actual = costs["actual", budget.scope, budget.target]
        estimate = costs["estimate", budget.scope, budget.target]
        budgets.append(
            {
                "id": budget.id,
                "scope": budget.scope,
                "target": budget.target,
                "version": budget.version,
                "editable": budget_access(trip, budget.scope, budget.target, actor_id),
                "amount": format_money(budget.amount_minor, base),
                "actual": format_money(actual, base),
                "estimated": format_money(estimate, base),
                "over_budget": actual > budget.amount_minor,
                "projected_over": actual + estimate > budget.amount_minor,
            }
        )
    for row in db.scalars(
        select(Settlement)
        .where(Settlement.trip_id == trip.id)
        .order_by(Settlement.created_at.desc())
    ):
        balances[members[row.from_user_id]["canonical_id"]] += row.amount_minor
        balances[members[row.to_user_id]["canonical_id"]] -= row.amount_minor
        settlements.append(
            {
                "id": row.id,
                "from_user_id": row.from_user_id,
                "to_user_id": row.to_user_id,
                "amount": format_money(row.amount_minor, base),
                "created_at": as_utc(row.created_at),
                "created_by": row.created_by,
                "version": row.version,
                "editable": history_manager(trip, row.created_by, members, actor_id),
            }
        )
    transfers = [
        {
            "from_user_id": who,
            "to_user_id": to,
            "amount": format_money(value, base),
            "can_record": actor_id in (who, to)
            or (
                actor_id == trip.owner_id
                and not members[who]["active"]
                and not members[to]["active"]
            ),
        }
        for who, to, value in suggested_transfers(balances)
    ]
    status = "settled" if not transfers else "partial" if settlements else "unsettled"
    return {
        "currency": base,
        "version": ledger.version if ledger else 0,
        "status": status,
        "members": members,
        "totals": {k: format_money(costs[k, "trip", ""], base) for k in ("estimate", "actual")},
        "expenses": expenses,
        "budgets": budgets,
        "settlements": settlements,
        "balances": {who: format_money(value, base) for who, value in balances.items()},
        "suggestions": transfers,
    }


@router.get("/finance")
def overview(trip_id: str, db: DB, user: Actor):
    return financial_state(db, require_member(db, trip_id, user.id, lock=True), user.id)


@router.post("/settlements", status_code=201)
async def settle(
    trip_id: str, payload: SettlementInput, db: DB, user: Actor, key: KeyHeader = None
):
    trip = require_member(db, trip_id, user.id, lock=True)
    existing, receipt = replay(db, trip_id, user.id, "settlement", payload, key)
    if existing:
        return {"id": existing}
    ledger = get_ledger(db, trip, True)
    check_version(ledger, payload.version)
    state = financial_state(db, trip, user.id)
    who, to = payload.from_user_id, payload.to_user_id
    if who == to or who not in state["balances"] or to not in state["balances"]:
        fail(422, "INVALID_SETTLEMENT", "請選擇兩位曾經加入此旅程的成員。")
    require_allowed(
        user.id in (who, to)
        or (
            user.id == trip.owner_id
            and not state["members"][who]["active"]
            and not state["members"][to]["active"]
        )
    )
    value = to_minor(payload.amount, ledger.currency)
    max_value = min(
        -to_minor(Decimal(state["balances"][who]), ledger.currency),
        to_minor(Decimal(state["balances"][to]), ledger.currency),
    )
    if value > max_value:
        fail(422, "SETTLEMENT_LIMIT", "還款金額超過雙方目前可結清的餘額。")
    row = Settlement(
        trip_id=trip_id, created_by=user.id, from_user_id=who, to_user_id=to, amount_minor=value
    )
    db.add(row)
    db.flush()
    return await finish(db, trip, user, ledger, row, "record", receipt)


@router.delete("/settlements/{settlement_id}")
async def undo_settlement(trip_id: str, settlement_id: str, version: int, db: DB, user: Actor):
    trip = require_member(db, trip_id, user.id, lock=True)
    row = item(db, Settlement, trip_id, settlement_id)
    require_allowed(history_manager(trip, row.created_by, people(db, trip_id), user.id))
    check_version(row, version)
    db.delete(row)
    return await finish(db, trip, user, get_ledger(db, trip), row, "undo")
