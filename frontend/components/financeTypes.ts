export type Rate = {
  id: string;
  source_currency: string;
  base_currency: string;
  rate: string;
  provider: string;
  rate_date: string;
  captured_at: string;
};
export type Expense = {
  id: string;
  title: string;
  category: string;
  incurred_on: string;
  kind: 'estimate' | 'actual';
  currency: string;
  amount: string;
  base_amount: string;
  rate: Rate;
  created_by: string;
  version: number;
  editable: boolean;
  split_mode: 'equal' | 'custom' | 'ratio';
  payers: Record<string, string>;
  splits: Record<string, { amount: string; weight: string }>;
};
export type Budget = {
  id: string;
  scope: 'trip' | 'category' | 'personal';
  target: string;
  amount: string;
  actual: string;
  estimated: string;
  over_budget: boolean;
  projected_over: boolean;
  editable: boolean;
  version: number;
};
export type Transfer = {
  from_user_id: string;
  to_user_id: string;
  amount: string;
  can_record: boolean;
};
export type Settlement = Omit<Transfer, 'can_record'> & {
  id: string;
  created_by: string;
  created_at: string;
  editable: boolean;
  version: number;
};
export type FinanceState = {
  currency: string;
  version: number;
  status: 'unsettled' | 'partial' | 'settled';
  members: Record<string, { nickname: string; active: boolean }>;
  totals: { actual: string; estimate: string };
  expenses: Expense[];
  budgets: Budget[];
  settlements: Settlement[];
  suggestions: Transfer[];
  balances: Record<string, string>;
};
export type Save = (
  path: string,
  method: string,
  payload?: Record<string, unknown>,
) => Promise<void>;
export function memberName(state: FinanceState, id: string) {
  const person = state.members[id];
  return person ? person.nickname + (person.active ? '' : '（已退出）') : '旅伴';
}
export function amountLabel(currency: string, value: string) {
  const [whole, fraction] = value.split('.');
  const formatted = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return currency + ' ' + formatted + (fraction === undefined ? '' : '.' + fraction);
}
