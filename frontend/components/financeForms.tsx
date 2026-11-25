'use client';

import { useRef, useState, type FormEvent } from 'react';
import { api } from '../lib/api';
import { errorText } from '../lib/trips';
import {
  type Budget,
  type Expense,
  type FinanceState,
  type Rate,
  type Save,
  type Transfer,
  memberName,
} from './financeTypes';

function localToday() {
  const date = new Date();
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export function ExpenseForm({
  tripId,
  state,
  userId,
  expense,
  save,
  busy,
}: {
  tripId: string;
  state: FinanceState;
  userId: string;
  expense?: Expense;
  save: Save;
  busy: boolean;
}) {
  const [currency, setCurrency] = useState(expense?.currency ?? state.currency);
  const [rate, setRate] = useState<Rate | null>(expense?.rate ?? null);
  const [rateMessage, setRateMessage] = useState('');
  const [loadingRate, setLoadingRate] = useState(false);
  const [manual, setManual] = useState('');
  const lookup = useRef(0);
  const [mode, setMode] = useState<Expense['split_mode']>(expense?.split_mode ?? 'equal');
  const [total, setTotal] = useState(expense?.amount ?? '');
  const [payers, setPayers] = useState<Record<string, string>>(expense?.payers ?? { [userId]: '' });
  const [splits, setSplits] = useState<Record<string, string>>(() =>
    expense
      ? Object.fromEntries(
          Object.entries(expense.splits).map(([id, s]) => [
            id,
            expense.split_mode === 'custom' ? s.amount : s.weight,
          ]),
        )
      : Object.fromEntries(
          Object.entries(state.members)
            .filter(([, m]) => m.active)
            .map(([id]) => [id, '1']),
        ),
  );
  function updateTotal(value: string) {
    setTotal(value);
    if (Object.keys(payers).length === 1) setPayers({ [Object.keys(payers)[0]]: value });
  }
  function toggle(values: Record<string, string>, who: string, selected: boolean, value: string) {
    const next = { ...values };
    if (selected) next[who] = value;
    else delete next[who];
    return next;
  }
  async function fetchRate() {
    const request = ++lookup.current;
    setLoadingRate(true);
    setRateMessage('');
    try {
      const result = await api<Rate>('/trips/' + tripId + '/finance/rates', 'POST', { currency });
      if (request === lookup.current) {
        setRate(result);
        setManual('');
      }
    } catch (e) {
      if (request === lookup.current) setRateMessage(errorText(e));
    } finally {
      if (request === lookup.current) setLoadingRate(false);
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await save('/expenses' + (expense ? '/' + expense.id : ''), expense ? 'PATCH' : 'POST', {
      title: form.get('title'),
      category: form.get('category'),
      kind: form.get('kind'),
      incurred_on: form.get('incurred_on'),
      currency,
      amount: total,
      rate_id: currency !== state.currency && rate ? rate.id : null,
      manual_rate: currency !== state.currency && !rate ? manual : null,
      split_mode: mode,
      payers,
      splits:
        mode === 'equal' ? Object.fromEntries(Object.keys(splits).map((id) => [id, '1'])) : splits,
      ...(expense ? { version: expense.version } : {}),
    });
  }
  const currencies = [
    'TWD',
    'JPY',
    'USD',
    'EUR',
    'GBP',
    'KRW',
    'HKD',
    'CNY',
    'SGD',
    'THB',
    'VND',
    'AUD',
    'CAD',
    'CHF',
    'KWD',
  ];
  return (
    <form className="fn-form" onSubmit={submit}>
      <label>
        費用名稱
        <input
          name="title"
          autoFocus
          required
          maxLength={160}
          defaultValue={expense?.title}
          placeholder="例如：京都車站至住宿車資"
        />
      </label>
      <div className="fn-fields">
        <label>
          支出類型
          <select name="kind" defaultValue={expense?.kind ?? 'actual'}>
            <option value="actual">實際支出</option>
            <option value="estimate">預估支出</option>
          </select>
        </label>
        <label>
          消費日期
          <input
            required
            name="incurred_on"
            type="date"
            defaultValue={expense?.incurred_on ?? localToday()}
          />
        </label>
        <label>
          費用類別
          <input
            required
            name="category"
            list="fn-categories"
            maxLength={80}
            defaultValue={expense?.category ?? '餐飲'}
          />
        </label>
        <label>
          幣別
          <input
            required
            aria-label="費用幣別"
            list="fn-currencies"
            maxLength={3}
            pattern="[A-Z]{3}"
            value={currency}
            onChange={(e) => {
              ++lookup.current;
              setCurrency(e.target.value.toUpperCase());
              setRate(null);
              setManual('');
              setRateMessage('');
              setLoadingRate(false);
            }}
          />
        </label>
      </div>
      <datalist id="fn-currencies">
        {currencies.map((code) => (
          <option key={code} value={code} />
        ))}
      </datalist>
      <datalist id="fn-categories">
        {[
          '餐飲',
          '住宿',
          '交通',
          '景點',
          '購物',
          '其他',
          ...state.budgets.filter((b) => b.scope === 'category').map((b) => b.target),
        ]
          .filter((c, i, a) => a.indexOf(c) === i)
          .map((c) => (
            <option key={c} value={c} />
          ))}
      </datalist>
      <label>
        費用總額（{currency}）
        <input
          required
          type="number"
          min="0.0001"
          step="any"
          value={total}
          onChange={(e) => updateTotal(e.target.value)}
        />
      </label>
      {currency !== state.currency && (
        <fieldset>
          <legend>換算至 {state.currency}</legend>
          <button type="button" disabled={currency.length !== 3 || loadingRate} onClick={fetchRate}>
            {loadingRate ? '取得中…' : '取得參考匯率'}
          </button>
          {rate && (
            <p>
              1 {currency} ＝ {rate.rate} {state.currency} · {rate.provider} · {rate.rate_date}
            </p>
          )}
          <label>
            手動匯率（每 1 {currency} 的 {state.currency} 金額）
            <input
              type="number"
              min="0.000000000001"
              step="any"
              required={!rate}
              value={manual}
              onChange={(e) => {
                ++lookup.current;
                setLoadingRate(false);
                setRate(null);
                setManual(e.target.value);
              }}
            />
          </label>
          {rateMessage && <p role="status">{rateMessage}</p>}
        </fieldset>
      )}
      <fieldset>
        <legend>付款人及墊付金額（{currency}）</legend>
        {Object.entries(state.members)
          .filter(([id, m]) => m.active || id in (expense?.payers ?? {}))
          .map(([id]) => (
            <div className="fn-member" key={id}>
              <label>
                <input
                  type="checkbox"
                  checked={id in payers}
                  onChange={(e) =>
                    setPayers(
                      toggle(payers, id, e.target.checked, Object.keys(payers).length ? '' : total),
                    )
                  }
                />
                {memberName(state, id)}
              </label>
              {id in payers && (
                <input
                  aria-label={memberName(state, id) + ' 墊付金額'}
                  type="number"
                  min="0.0001"
                  step="any"
                  required
                  value={payers[id]}
                  onChange={(e) => setPayers({ ...payers, [id]: e.target.value })}
                />
              )}
            </div>
          ))}
      </fieldset>
      <fieldset>
        <legend>分攤成員</legend>
        <label>
          分攤方式
          <select value={mode} onChange={(e) => setMode(e.target.value as Expense['split_mode'])}>
            <option value="equal">平均分攤</option>
            <option value="custom">自訂金額</option>
            <option value="ratio">依比例分攤</option>
          </select>
        </label>
        {Object.entries(state.members)
          .filter(([id, m]) => m.active || id in (expense?.splits ?? {}))
          .map(([id]) => (
            <div className="fn-member" key={id}>
              <label>
                <input
                  type="checkbox"
                  checked={id in splits}
                  onChange={(e) =>
                    setSplits(toggle(splits, id, e.target.checked, mode === 'custom' ? '' : '1'))
                  }
                />
                {memberName(state, id)}
              </label>
              {id in splits && mode !== 'equal' && (
                <input
                  aria-label={
                    memberName(state, id) + (mode === 'ratio' ? ' 分攤權重' : ' 分攤金額')
                  }
                  type="number"
                  min={mode === 'ratio' ? '0.000001' : '0'}
                  step="any"
                  required
                  value={splits[id]}
                  onChange={(e) => setSplits({ ...splits, [id]: e.target.value })}
                />
              )}
            </div>
          ))}
      </fieldset>
      <button
        className="fn-primary"
        disabled={busy || loadingRate || !Object.keys(payers).length || !Object.keys(splits).length}
      >
        儲存費用
      </button>
    </form>
  );
}

export function BudgetForm({
  state,
  owner,
  budget,
  save,
  busy,
}: {
  state: FinanceState;
  owner: boolean;
  budget?: Budget;
  save: Save;
  busy: boolean;
}) {
  const [scope, setScope] = useState(budget?.scope ?? (owner ? 'trip' : 'personal'));
  return (
    <form
      className="fn-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const values = new FormData(e.currentTarget);
        await save(
          '/budgets' + (budget ? '/' + budget.id : ''),
          budget ? 'PATCH' : 'POST',
          budget
            ? { amount: values.get('amount'), version: budget.version }
            : {
                scope,
                category: scope === 'category' ? values.get('category') : null,
                amount: values.get('amount'),
              },
        );
      }}
    >
      <label>
        預算範圍
        <select
          value={scope}
          disabled={!!budget}
          onChange={(e) => setScope(e.target.value as Budget['scope'])}
        >
          {owner && <option value="trip">整趟旅程</option>}
          <option value="personal">我的個人預算</option>
          {owner && <option value="category">費用類別</option>}
        </select>
      </label>
      {scope === 'category' && (
        <label>
          類別名稱
          <input
            required
            maxLength={80}
            name="category"
            defaultValue={budget?.target}
            disabled={!!budget}
            placeholder="例如：住宿"
          />
        </label>
      )}
      <label>
        預算額度（{state.currency}）
        <input
          type="number"
          required
          min="0.0001"
          step="any"
          name="amount"
          defaultValue={budget?.amount}
        />
      </label>
      <button className="fn-primary" disabled={busy}>
        儲存預算
      </button>
    </form>
  );
}

export function RepaymentForm({
  state,
  transfer,
  save,
  busy,
}: {
  state: FinanceState;
  transfer: Transfer;
  save: Save;
  busy: boolean;
}) {
  const [version] = useState(state.version);
  return (
    <form
      className="fn-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const values = new FormData(e.currentTarget);
        await save('/settlements', 'POST', {
          from_user_id: transfer.from_user_id,
          to_user_id: transfer.to_user_id,
          amount: values.get('amount'),
          version,
        });
      }}
    >
      <p>
        {memberName(state, transfer.from_user_id)} 還款給 {memberName(state, transfer.to_user_id)}
      </p>
      <label>
        已還金額（{state.currency}）
        <input
          required
          type="number"
          min="0.0001"
          max={transfer.amount}
          step="any"
          name="amount"
          defaultValue={transfer.amount}
        />
      </label>
      <button className="fn-primary" disabled={busy}>
        記錄還款
      </button>
    </form>
  );
}
