from datetime import date
from decimal import Decimal

from app import finance_money
from app.finance_money import allocate, format_money, suggested_transfers, to_minor


def expense(owner_id, guest_id, **overrides):
    return {
        "title": "午餐",
        "incurred_on": "2026-11-20",
        "category": "餐飲",
        "kind": "actual",
        "currency": "TWD",
        "amount": "100",
        "payers": {owner_id: "70", guest_id: "30"},
        "split_mode": "custom",
        "splits": {owner_id: "20", guest_id: "80"},
        **overrides,
    }


def test_budgets_settlements_and_idempotence(owner, guest, trip):
    root = "/api/v1/trips/" + trip["id"]
    a, b = [client.get("/api/v1/auth/me").json()["id"] for client in (owner, guest)]
    assert guest.post(root + "/budgets", json={"scope": "trip", "amount": "100"}).status_code == 403
    for payload in (
        {"scope": "trip", "amount": "80"},
        {"scope": "category", "category": "餐飲", "amount": "80"},
    ):
        assert owner.post(root + "/budgets", json=payload).status_code == 201
    assert (
        guest.post(root + "/budgets", json={"scope": "personal", "amount": "70"}).status_code == 201
    )
    payload = expense(a, b, request_id="receipt-a")
    first = owner.post(root + "/expenses", json=payload)
    assert first.status_code == 201, first.text
    assert owner.post(root + "/expenses", json=payload).json() == first.json()
    assert (
        owner.post(root + "/expenses", json={**payload, "title": "重複識別碼"}).status_code == 409
    )
    estimate = expense(a, b, kind="estimate")
    assert owner.post(root + "/expenses", json=estimate).status_code == 201
    state = guest.get(root + "/finance").json()
    assert state["status"] == "unsettled" and state["totals"] == {
        "actual": "100.00",
        "estimate": "100.00",
    }
    assert state["balances"] == {a: "50.00", b: "-50.00"}
    assert all(budget["over_budget"] for budget in state["budgets"])
    assert len(owner.get(root + "/finance").json()["budgets"]) == 2
    payment = {
        "from_user_id": b,
        "to_user_id": a,
        "amount": "20",
        "version": state["version"],
        "request_id": "repayment-1",
    }
    assert guest.post(root + "/settlements", json=payment).status_code == 201
    assert guest.post(root + "/settlements", json=payment).status_code == 201
    assert (
        guest.post(root + "/settlements", json={**payment, "request_id": "new"}).status_code == 409
    )
    state = guest.get(root + "/finance").json()
    assert (
        state["status"] == "partial"
        and state["suggestions"][0]["amount"] == "30.00"
        and len(state["settlements"]) == 1
    )
    assert (
        owner.post(
            root + "/settlements",
            json={**payment, "amount": "31", "version": state["version"], "request_id": "bad"},
        ).status_code
        == 422
    )
    assert (
        owner.post(
            root + "/settlements",
            json={**payment, "amount": "30", "version": state["version"], "request_id": "good"},
        ).status_code
        == 201
    )
    assert owner.get(root + "/finance").json()["status"] == "settled"


def test_fx_snapshot_precision_and_departed_history(owner, guest, trip, monkeypatch):
    root = "/api/v1/trips/" + trip["id"]
    a, b = [client.get("/api/v1/auth/me").json()["id"] for client in (owner, guest)]

    async def quote(source, target):
        assert (source, target) == ("JPY", "TWD")
        return "0.21999", date(2026, 11, 19)

    monkeypatch.setattr(finance_money, "reference_rate", quote)
    rate = guest.post(root + "/finance/rates", json={"currency": "JPY"}).json()
    payload = expense(
        a,
        b,
        currency="JPY",
        amount="101",
        payers={a: "101"},
        splits={a: "1", b: "2"},
        split_mode="ratio",
        rate_id=rate["id"],
    )
    result = guest.post(root + "/expenses", json=payload)
    assert result.status_code == 201, result.text
    data = guest.get(root + "/finance").json()
    original = data["expenses"][0]
    assert original["base_amount"] == "22.22" and original["rate"]["provider"] == "Frankfurter"
    assert original["rate"]["rate_date"] == "2026-11-19" and original["rate"]["captured_at"]
    assert original["splits"][a]["amount"] == "34" and original["splits"][b]["amount"] == "67"
    url = root + "/expenses/" + result.json()["id"]
    assert owner.patch(url, json={**payload, "version": 1}).status_code == 403
    assert (
        guest.patch(
            url, json={**payload, "amount": "101.5", "payers": {a: "101.5"}, "version": 1}
        ).status_code
        == 422
    )
    assert guest.patch(url, json={**payload, "version": 1, "title": "修改"}).status_code == 200
    assert guest.patch(url, json={**payload, "version": 1}).status_code == 409
    assert owner.delete(root + "/members/" + b).status_code == 204
    assert guest.get(root + "/finance").status_code == 403
    data = owner.get(root + "/finance").json()
    assert not data["members"][b]["active"] and data["expenses"][0]["editable"]
    assert (
        data["expenses"][0]["created_by"] == b and data["expenses"][0]["rate"] == original["rate"]
    )
    assert owner.patch(url, json={**payload, "version": 2}).status_code == 200
    assert owner.post(root + "/expenses", json=payload).status_code == 422
    assert (
        owner.patch(root, json={"currency": "USD", "version": trip["version"]}).status_code == 200
    )
    assert owner.get(root + "/finance").json()["currency"] == "TWD"


def test_manual_fx_and_member_validation(owner, guest, trip):
    root = "/api/v1/trips/" + trip["id"]
    a, b = [c.get("/api/v1/auth/me").json()["id"] for c in (owner, guest)]
    data = expense(
        a, b, currency="KWD", amount="0.001", payers={a: "0.001"}, split_mode="equal", splits={b: 1}
    )
    assert owner.post(root + "/expenses", json=data).status_code == 422
    result = owner.post(root + "/expenses", json={**data, "manual_rate": "103.123456789123"})
    assert result.status_code == 201, result.text
    row = owner.get(root + "/finance").json()["expenses"][0]
    assert row["base_amount"] == "0.10" and row["rate"]["rate"] == "103.123456789123"
    assert (
        owner.post(root + "/expenses", json=expense(a, b, splits={a: "99", b: "2"})).status_code
        == 422
    )
    assert (
        owner.post(root + "/expenses", json=expense(a, b, payers={"outsider": "100"})).status_code
        == 422
    )
    assert owner.delete(root + "/expenses/" + row["id"] + "?version=1").status_code == 200
    assert not owner.get(root + "/finance").json()["expenses"]


def test_integer_rounding_and_netting():
    assert allocate(5, {"a": 1, "b": 1, "c": 1}) == {"a": 2, "b": 2, "c": 1}
    assert to_minor(Decimal("1.23455"), "CLF", rounded=True) == 12346
    assert format_money(123, "JPY") == "123"
    balances = {"a": 67, "b": 33, "c": -50, "d": -50}
    transfers = suggested_transfers(balances)
    for who, to, n in transfers:
        balances[who] += n
        balances[to] -= n
    assert all(n == 0 for n in balances.values()) and len(transfers) <= 3
