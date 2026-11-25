'use client';

import { useEffect, useRef, useState } from 'react';
import { ArrowDownLeft, ArrowRight, ArrowUpRight, Plus, ReceiptText, Wallet } from 'lucide-react';
import { api, ApiError } from '../lib/api';
import { errorText, type Member, type Trip } from '../lib/trips';
import { Modal } from './ui/dialog';
import { AttachmentButton } from './Attachments';
import { BudgetForm, ExpenseForm, RepaymentForm } from './financeForms';
import {
  amountLabel,
  memberName,
  type Budget,
  type Expense,
  type FinanceState,
  type Save,
  type Transfer,
} from './financeTypes';
import './finance.css';

type Props = {
  trip: Trip;
  userId: string;
  members: Member[];
  refresh: number;
  onChange: () => void;
  setError: (error: string) => void;
};
type Dialog =
  | { type: 'expense'; item?: Expense }
  | { type: 'budget'; item?: Budget }
  | { type: 'repayment'; item: Transfer }
  | { type: 'remove'; path: string; label: string };
const statusLabel = { unsettled: '未結清', partial: '部分結清', settled: '已結清' };

export default function Finance({ trip, userId, refresh, onChange, setError }: Props) {
  const [state, setState] = useState<FinanceState | null>(null);
  const [tick, setTick] = useState(0);
  const [loadError, setLoadError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [formError, setFormError] = useState('');
  const last = useRef({ key: '', body: '' });
  const root = '/trips/' + trip.id;
  useEffect(() => {
    let active = true;
    api<FinanceState>(root + '/finance')
      .then((data) => {
        if (active) {
          setState(data);
          setLoadError('');
        }
      })
      .catch((err) => {
        if (active) setLoadError(errorText(err));
      });
    return () => {
      active = false;
    };
  }, [root, refresh, tick]);
  function show(next: Dialog) {
    setFormError('');
    last.current = { key: '', body: '' };
    setDialog(next);
  }
  const save: Save = async (path, method, payload) => {
    let body = payload;
    if (method === 'POST' && payload) {
      const content = JSON.stringify([path, payload]);
      if (last.current.body !== content) last.current = { body: content, key: crypto.randomUUID() };
      body = { ...payload, request_id: last.current.key };
    }
    setBusy(true);
    setFormError('');
    try {
      await api(root + path, method, body);
      setDialog(null);
      setTick((n) => n + 1);
      setMessage('旅費紀錄已更新。');
      onChange();
    } catch (err) {
      setFormError(errorText(err));
      if (err instanceof ApiError && err.status === 409) setTick((n) => n + 1);
      if (err instanceof ApiError && [401, 403].includes(err.status)) setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };
  if (!state)
    return (
      <div className="fn-panel" role="status">
        {loadError || '正在載入旅費…'}
        {loadError && <button onClick={() => setTick((n) => n + 1)}>重試</button>}
      </div>
    );
  const money = (value: string) => amountLabel(state.currency, value);
  const name = (id: string) => memberName(state, id);
  const labelBudget = (budget: Budget) =>
    budget.scope === 'personal'
      ? '我的個人預算'
      : budget.scope === 'trip'
        ? '旅程總預算'
        : budget.target;
  return (
    <section className="fn-root">
      <div className="fn-head">
        <div>
          <h2>預算與分帳</h2>
          <p>記帳幣別 {state.currency}</p>
        </div>
        <button className="fn-primary" onClick={() => show({ type: 'expense' })}>
          <Plus size={17} />
          新增費用
        </button>
      </div>
      {loadError && (
        <p role="alert">
          {loadError} <button onClick={() => setTick((n) => n + 1)}>重試</button>
        </p>
      )}
      <div className="fn-totals">
        <div>
          <span>
            <ReceiptText size={16} />
            實際支出
          </span>
          <strong>{money(state.totals.actual)}</strong>
        </div>
        <div>
          <span>
            <Wallet size={16} />
            預估支出
          </span>
          <strong>{money(state.totals.estimate)}</strong>
        </div>
      </div>
      <section className="fn-panel">
        <div className="fn-head">
          <h3>預算</h3>
          <button onClick={() => show({ type: 'budget' })}>設定預算</button>
        </div>
        {!state.budgets.length && <p>尚未設定預算。</p>}
        {state.budgets.map((b) => (
          <div key={b.id} className="fn-row">
            <div>
              <b>{labelBudget(b)}</b>
              <p>
                已用 {money(b.actual)} ／ {money(b.amount)}
              </p>
              {b.over_budget ? (
                <small className="fn-warning">實際支出已超出預算</small>
              ) : b.projected_over ? (
                <small className="fn-warning">加上預估支出將超出預算</small>
              ) : null}
            </div>
            {b.editable && (
              <div className="fn-actions">
                <button onClick={() => show({ type: 'budget', item: b })}>調整</button>
                <button
                  onClick={() =>
                    show({
                      type: 'remove',
                      path: '/budgets/' + b.id + '?version=' + b.version,
                      label: labelBudget(b),
                    })
                  }
                >
                  移除
                </button>
              </div>
            )}
          </div>
        ))}
      </section>
      <section className="fn-panel">
        <h3>費用明細</h3>
        {!state.expenses.length && <p>尚未記帳。</p>}
        {state.expenses.map((e) => (
          <details className="fn-entry" key={e.id}>
            <summary>
              <span>
                <b>{e.title}</b>
                <small>
                  {e.incurred_on} · {e.category} · {e.kind === 'actual' ? '實際' : '預估'}
                </small>
              </span>
              <strong>{amountLabel(e.currency, e.amount)}</strong>
            </summary>
            <p>
              付款人　
              {Object.entries(e.payers)
                .map(([id, v]) => name(id) + ' ' + amountLabel(e.currency, v))
                .join('、')}
            </p>
            <p>
              分攤　
              {Object.entries(e.splits)
                .map(([id, s]) => name(id) + ' ' + amountLabel(e.currency, s.amount))
                .join('、')}
            </p>
            <p>記錄者　{name(e.created_by)}</p>
            <AttachmentButton tripId={trip.id} kind="expense" targetId={e.id} />
            {e.currency !== state.currency && (
              <p>
                換算 {money(e.base_amount)} · 匯率 {e.rate.rate} ·{' '}
                {e.rate.provider === 'manual' ? '手動' : e.rate.provider} · 匯率日{' '}
                {e.rate.rate_date} · 保存於 {new Date(e.rate.captured_at).toLocaleString('zh-TW')}
              </p>
            )}
            {e.editable && (
              <div className="fn-actions">
                <button onClick={() => show({ type: 'expense', item: e })}>編輯費用</button>
                <button
                  onClick={() =>
                    show({
                      type: 'remove',
                      path: '/expenses/' + e.id + '?version=' + e.version,
                      label: e.title,
                    })
                  }
                >
                  刪除費用
                </button>
              </div>
            )}
          </details>
        ))}
      </section>
      <section className="fn-panel">
        <div className="fn-head">
          <h3>淨額與還款</h3>
          {state.expenses.some((e) => e.kind === 'actual') && (
            <span className="fn-status">{statusLabel[state.status]}</span>
          )}
        </div>
        {Object.entries(state.balances).map(([id, value]) => (
          <div className="fn-row" key={id}>
            <span>{name(id)}</span>
            <span className="fn-net">
              {value.startsWith('-') ? (
                <>
                  <ArrowUpRight size={16} />
                  應付 {money(value.slice(1))}
                </>
              ) : Number(value) > 0 ? (
                <>
                  <ArrowDownLeft size={16} />
                  應收 {money(value)}
                </>
              ) : (
                '已平衡'
              )}
            </span>
          </div>
        ))}
        {state.suggestions.length > 0 && (
          <>
            <h4>還款建議</h4>
            {state.suggestions.map((s) => (
              <div className="fn-row" key={s.from_user_id + s.to_user_id}>
                <span>
                  {name(s.from_user_id)} <ArrowRight size={14} /> {name(s.to_user_id)} ·{' '}
                  {money(s.amount)}
                </span>
                {s.can_record && (
                  <button onClick={() => show({ type: 'repayment', item: s })}>記錄還款</button>
                )}
              </div>
            ))}
          </>
        )}
        {state.settlements.length > 0 && (
          <>
            <h4>還款紀錄</h4>
            {state.settlements.map((s) => (
              <div className="fn-row" key={s.id}>
                <div>
                  {name(s.from_user_id)} → {name(s.to_user_id)} · {money(s.amount)}
                  <p>
                    {new Date(s.created_at).toLocaleDateString('zh-TW')} · {name(s.created_by)} 記錄
                  </p>
                </div>
                {s.editable && (
                  <button
                    onClick={() =>
                      show({
                        type: 'remove',
                        path: '/settlements/' + s.id + '?version=' + s.version,
                        label: '這筆還款紀錄',
                      })
                    }
                  >
                    撤銷
                  </button>
                )}
              </div>
            ))}
          </>
        )}
      </section>
      {message && <p role="status">{message}</p>}
      {dialog && (
        <Modal
          title={
            dialog.type === 'expense'
              ? dialog.item
                ? '編輯費用'
                : '新增費用'
              : dialog.type === 'budget'
                ? '設定預算'
                : dialog.type === 'repayment'
                  ? '記錄已完成的還款'
                  : '確認移除'
          }
          onClose={() => {
            if (!busy) setDialog(null);
          }}
        >
          {formError && (
            <p className="fn-warning" role="alert">
              {formError}
            </p>
          )}
          {dialog.type === 'expense' && (
            <ExpenseForm
              tripId={trip.id}
              state={state}
              userId={userId}
              expense={dialog.item}
              save={save}
              busy={busy}
            />
          )}
          {dialog.type === 'budget' && (
            <BudgetForm
              state={state}
              owner={trip.owner_id === userId}
              budget={dialog.item}
              save={save}
              busy={busy}
            />
          )}
          {dialog.type === 'repayment' && (
            <RepaymentForm state={state} transfer={dialog.item} save={save} busy={busy} />
          )}
          {dialog.type === 'remove' && (
            <div className="fn-form">
              <p>移除「{dialog.label}」後將重新計算旅費餘額。</p>
              <button disabled={busy} onClick={() => save(dialog.path, 'DELETE')}>
                確認移除
              </button>
            </div>
          )}
        </Modal>
      )}
    </section>
  );
}
