'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  Check,
  ChevronDown,
  CirclePlus,
  LockKeyhole,
  MapPin,
  MessageCircle,
  Pencil,
  Plus,
  Reply,
  Send,
  UsersRound,
  Vote,
} from 'lucide-react';
import { api } from '../lib/api';
import './decisions.css';

type Option = { id: string; text: string; place_id: string | null };
type Result = {
  counts: Record<string, number>;
  winners: string[];
  ballots: { user_id: string; nickname: string; option_ids: string[] }[];
};
type Round = {
  id: string;
  number: number;
  title: string;
  kind: 'date' | 'place';
  mode: 'single' | 'multiple';
  closed: boolean;
  deadline: string | null;
  options: Option[];
  my_choices: string[];
  ballot_version: number;
  review_needed: boolean;
  results?: Result;
};
type Poll = {
  id: string;
  created_by: string;
  editable_by: string;
  version: number;
  rounds: Round[];
};
type Comment = {
  id: string;
  author_id: string;
  nickname: string;
  content: string;
  parent_id: string | null;
  created_at: string;
  updated_at: string | null;
  version: number;
  deleted: boolean;
};
type Day = { id: string; day_number: number; title: string };
type Place = { id: string; name: string; candidate: boolean };
type Props = {
  tripId: string;
  userId: string;
  isOwner: boolean;
  section: 'polls' | 'comments';
  refresh: number;
  onChange: () => void;
  setError: (message: string) => void;
};
type Save = (url: string, method: string, body: unknown, notice: string) => Promise<boolean>;

function localTime(value: string) {
  return new Date(value).toLocaleString('zh-TW', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function inputDateTime(value: string | null) {
  if (!value) return '';
  const date = new Date(value);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function formData(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  return new FormData(event.currentTarget);
}

function Results({ round }: { round: Round }) {
  const results = round.results;
  if (!results) return null;
  if (!results.ballots.length) return <p className="dc-note">無結果，本輪未收到選票。</p>;
  const nameOf = (id: string) => round.options.find((o) => o.id === id)?.text;
  return (
    <div className="dc-results">
      <p className="dc-result-title">
        {results.winners.length > 1 ? '平票' : '勝出選項'} ·{' '}
        {results.winners.map(nameOf).join('、')}
      </p>
      {round.options.map((o) => (
        <div className="dc-result-line" key={o.id}>
          <span>{o.text}</span>
          <b>{results.counts[o.id]} 票</b>
          <progress
            aria-label={o.text + ' 得票'}
            max={results.ballots.length}
            value={results.counts[o.id]}
          />
        </div>
      ))}
      <details>
        <summary>
          <UsersRound size={15} /> 成員選票（{results.ballots.length}）
        </summary>
        <ul>
          {results.ballots.map((b) => (
            <li key={b.user_id}>
              <strong>{b.nickname}</strong>　{b.option_ids.map(nameOf).join('、')}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function CreatePoll({
  tripId,
  places,
  save,
  cancel,
}: {
  tripId: string;
  places: Place[];
  save: Save;
  cancel: () => void;
}) {
  const [kind, setKind] = useState('place');
  const [options, setOptions] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    const data = formData(event);
    const deadline = String(data.get('deadline') || '');
    const entries = options
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const ok = await save(
      '/trips/' + tripId + '/polls',
      'POST',
      {
        title: data.get('title'),
        kind,
        mode: data.get('mode'),
        deadline: deadline ? new Date(deadline).toISOString() : null,
        options: entries.map((text) => ({
          text,
          place_id: kind === 'place' ? places.find((p) => p.name === text)?.id : undefined,
        })),
      },
      '已發起投票',
    );
    if (ok) cancel();
  }
  return (
    <form className="dc-panel dc-form" onSubmit={submit}>
      <h3>發起投票</h3>
      <label>
        投票主題
        <input
          name="title"
          required
          maxLength={180}
          autoFocus
          placeholder="這趟旅程想一起決定什麼？"
        />
      </label>
      <div className="dc-cols">
        <label>
          投票類型
          <select
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setOptions('');
            }}
          >
            <option value="place">景點投票</option>
            <option value="date">日期投票</option>
          </select>
        </label>
        <label>
          選票方式
          <select name="mode">
            <option value="single">單選</option>
            <option value="multiple">多選</option>
          </select>
        </label>
      </div>
      <label>
        候選選項（每行一個，至少兩個）
        <textarea
          rows={3}
          required
          value={options}
          onChange={(e) => setOptions(e.target.value)}
          placeholder={
            kind === 'date' ? '2027-04-03 ~ 2027-04-05\n2027-04-10 ~ 2027-04-12' : '輸入景點名稱'
          }
        />
      </label>
      {kind === 'place' && places.length > 0 && (
        <label>
          從景點清單加入
          <select
            value=""
            onChange={(e) => {
              const text = places.find((p) => p.id === e.target.value)?.name;
              if (
                text &&
                !options
                  .split('\n')
                  .map((s) => s.trim())
                  .includes(text)
              )
                setOptions(options.trimEnd() + (options.trim() ? '\n' : '') + text);
            }}
          >
            <option value="">選擇景點</option>
            {places
              .filter((p) => p.candidate)
              .map((p) => (
                <option value={p.id} key={p.id}>
                  {p.name}
                </option>
              ))}
          </select>
        </label>
      )}
      <label>
        截止時間（選填）
        <input type="datetime-local" name="deadline" />
      </label>
      <div className="dc-actions">
        <button className="dc-primary">
          <Plus size={16} /> 發起投票
        </button>
        <button type="button" onClick={cancel}>
          取消
        </button>
      </div>
    </form>
  );
}

function PollCard({
  poll,
  userId,
  days,
  save,
}: {
  poll: Poll;
  userId: string;
  days: Day[];
  save: Save;
}) {
  const round = poll.rounds[0];
  const [editing, setEditing] = useState<{ round: Round; version: number } | null>(null);
  const path = '/polls/' + poll.id;
  const author = poll.editable_by === userId;
  const winners = round.results?.winners ?? [];
  const version = poll.version;
  async function submitVote(event: FormEvent<HTMLFormElement>) {
    const data = formData(event);
    await save(
      path + '/ballot',
      'PUT',
      { version, ballot_version: round.ballot_version, option_ids: data.getAll('choice') },
      '已儲存你的選票',
    );
  }
  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    const data = formData(event);
    const deadline = String(data.get('deadline') || '');
    if (
      editing &&
      (await save(
        path,
        'PATCH',
        {
          version: editing.version,
          title: data.get('title'),
          mode: data.get('mode'),
          deadline: deadline ? new Date(deadline).toISOString() : null,
        },
        '已更新投票',
      ))
    )
      setEditing(null);
  }
  return (
    <article className="dc-panel dc-card">
      <div className="dc-card-top">
        <span className={'dc-status ' + (round.closed ? 'dc-closed' : '')}>
          {round.closed ? '已結束' : '投票中'}
        </span>
        <small>
          第 {round.number} 輪 · {round.kind === 'date' ? '日期' : '景點'} ·{' '}
          {round.mode === 'single' ? '單選' : '多選'}
        </small>
      </div>
      <h3>{round.title}</h3>
      {round.deadline && <small>截止於 {localTime(round.deadline)}</small>}
      {round.review_needed && (
        <p role="status" className="dc-alert">
          旅伴新增了選項，請重新檢視並儲存你的選票。
        </p>
      )}
      {!round.closed && (
        <form key={round.id + '-' + round.ballot_version} onSubmit={submitVote}>
          <fieldset className="dc-choices">
            <legend className="dc-sr">
              選擇{round.mode === 'single' ? '一個' : '一個或多個'}選項
            </legend>
            {round.options.map((o) => (
              <label className="dc-choice" key={o.id}>
                <input
                  name="choice"
                  value={o.id}
                  type={round.mode === 'single' ? 'radio' : 'checkbox'}
                  defaultChecked={round.my_choices.includes(o.id)}
                  required={round.mode === 'single'}
                />
                <span>{o.text}</span>
              </label>
            ))}
          </fieldset>
          <div className="dc-vote-footer">
            <small>
              <LockKeyhole size={13} /> 截止後公開選票
            </small>
            <button className="dc-primary">
              <Check size={15} /> {round.ballot_version ? '更新選票' : '送出選票'}
            </button>
          </div>
        </form>
      )}
      <Results round={round} />
      {!round.closed && (
        <details className="dc-controls">
          <summary>
            <CirclePlus size={15} /> 補充候選選項
          </summary>
          <form
            className="dc-inline"
            onSubmit={async (event) => {
              const form = event.currentTarget;
              const data = formData(event);
              if (
                await save(
                  path + '/options',
                  'POST',
                  { version, text: data.get('text') },
                  '已新增選項並提醒已投票的旅伴',
                )
              )
                form.reset();
            }}
          >
            <input
              aria-label="新選項"
              name="text"
              required
              maxLength={150}
              placeholder={round.kind === 'date' ? 'YYYY-MM-DD 或日期區間' : '新景點名稱'}
            />
            <button>加入選項</button>
          </form>
        </details>
      )}
      {round.closed &&
        winners.length === 1 &&
        (days.length > 0 ? (
          <form
            className="dc-inline dc-controls"
            onSubmit={async (event) => {
              const data = formData(event);
              await save(
                path + '/adopt',
                'POST',
                { version, option_id: winners[0], day_id: data.get('day') },
                '已將勝出選項加入行程',
              );
            }}
          >
            <label className="dc-grow">
              將勝出選項加入
              <select name="day">
                {days.map((d) => (
                  <option key={d.id} value={d.id}>
                    Day {d.day_number}
                    {d.title ? ' · ' + d.title : ''}
                  </option>
                ))}
              </select>
            </label>
            <button>
              <MapPin size={15} /> 採用至行程
            </button>
          </form>
        ) : (
          <p className="dc-note">先在每日行程新增一天，即可採用勝出選項。</p>
        ))}
      {author && (
        <div className="dc-controls dc-actions">
          {!round.closed && (
            <button onClick={() => setEditing({ round, version })}>
              <Pencil size={14} /> 編輯規則
            </button>
          )}
          <button
            onClick={() => {
              if (round.closed || window.confirm('確定結束本輪並公開個別成員選票？')) {
                void save(
                  path + (round.closed ? '/reopen' : '/close'),
                  'POST',
                  { version },
                  round.closed ? '已開啟新一輪' : '本輪投票已結束',
                );
              }
            }}
          >
            {round.closed ? '開啟新一輪' : '結束本輪'}
          </button>
          <button
            className="dc-danger"
            onClick={() => {
              if (window.confirm('刪除這個投票和所有輪次的紀錄？'))
                void save(path, 'DELETE', { version }, '已刪除投票');
            }}
          >
            刪除投票
          </button>
        </div>
      )}
      {editing && editing.round.id === round.id && !round.closed && (
        <form className="dc-form dc-controls" onSubmit={submitEdit}>
          <label>
            投票主題
            <input name="title" required defaultValue={editing.round.title} maxLength={180} />
          </label>
          <div className="dc-cols">
            <label>
              選票方式
              <select name="mode" defaultValue={editing.round.mode}>
                <option value="single">單選</option>
                <option value="multiple">多選</option>
              </select>
            </label>
            <label>
              截止時間
              <input
                name="deadline"
                type="datetime-local"
                defaultValue={inputDateTime(editing.round.deadline)}
              />
            </label>
          </div>
          <div className="dc-actions">
            <button className="dc-primary">儲存規則</button>
            <button type="button" onClick={() => setEditing(null)}>
              取消
            </button>
          </div>
        </form>
      )}
      {poll.rounds.length > 1 && (
        <details className="dc-controls">
          <summary>
            <ChevronDown size={15} /> 歷次投票結果（{poll.rounds.length - 1}）
          </summary>
          {poll.rounds.slice(1).map((r) => (
            <div key={r.id} className="dc-history">
              <h4>
                第 {r.number} 輪 · {r.title}
              </h4>
              <Results round={r} />
            </div>
          ))}
        </details>
      )}
    </article>
  );
}

function Discussion({
  comments,
  userId,
  isOwner,
  tripId,
  save,
}: {
  comments: Comment[];
  userId: string;
  isOwner: boolean;
  tripId: string;
  save: Save;
}) {
  const [target, setTarget] = useState<{ comment: Comment; type: 'edit' | 'reply' } | null>(null);
  const [draft, setDraft] = useState('');
  const input = useRef<HTMLTextAreaElement>(null);
  function start(comment: Comment, type: 'edit' | 'reply') {
    setTarget({ comment, type });
    setDraft(type === 'edit' ? comment.content : '');
    input.current?.focus();
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    const ok =
      target?.type === 'edit'
        ? await save(
            '/comments/' + target.comment.id,
            'PATCH',
            { content, version: target.comment.version },
            '已更新留言',
          )
        : await save(
            '/trips/' + tripId + '/comments',
            'POST',
            { content, parent_id: target?.comment.id },
            '已送出留言',
          );
    if (ok) {
      setTarget(null);
      setDraft('');
    }
  }
  const threads = new Map(comments.map((c) => [c.id, c]));
  return (
    <>
      <div className="dc-heading">
        <h2>旅程討論</h2>
        <small>{comments.filter((c) => !c.deleted).length} 則留言</small>
      </div>
      <form className="dc-panel dc-form" onSubmit={submit}>
        <label>
          {target
            ? target.type === 'edit'
              ? '編輯你的留言'
              : '回覆 ' + target.comment.nickname
            : '新增留言'}
          <textarea
            required
            maxLength={5000}
            ref={input}
            rows={3}
            placeholder="和旅伴分享你的想法…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
        </label>
        <div className="dc-actions">
          <button className="dc-primary" disabled={!draft.trim()}>
            <Send size={15} /> {target?.type === 'edit' ? '儲存修改' : '送出留言'}
          </button>
          {target && (
            <button
              type="button"
              onClick={() => {
                setTarget(null);
                setDraft('');
              }}
            >
              取消
            </button>
          )}
        </div>
      </form>
      {!comments.length && (
        <div className="dc-empty">
          <MessageCircle size={30} />
          <h3>留下第一則留言</h3>
        </div>
      )}
      {comments.map((c) => {
        const parent = c.parent_id ? threads.get(c.parent_id) : undefined;
        return (
          <article className="dc-panel dc-comment" key={c.id}>
            <div className="dc-author">
              <span className="dc-avatar" aria-hidden>
                {Array.from(c.nickname)[0]}
              </span>
              <div>
                <strong>{c.nickname}</strong>
                <small>
                  {localTime(c.created_at)}
                  {c.updated_at && !c.deleted ? ' · 已編輯' : ''}
                </small>
              </div>
            </div>
            {parent && (
              <blockquote>
                回覆 {parent.nickname} · {parent.deleted ? '留言已刪除' : parent.content}
              </blockquote>
            )}
            <p>{c.deleted ? '此留言已刪除' : c.content}</p>
            {!c.deleted && (
              <div className="dc-actions">
                <button onClick={() => start(c, 'reply')}>
                  <Reply size={14} /> 回覆
                </button>
                {c.author_id === userId && (
                  <button onClick={() => start(c, 'edit')}>
                    <Pencil size={14} /> 編輯
                  </button>
                )}
                {(c.author_id === userId || isOwner) && (
                  <button
                    className="dc-danger"
                    onClick={() => {
                      if (window.confirm('確定刪除這則留言？'))
                        void save(
                          '/comments/' + c.id,
                          'DELETE',
                          { version: c.version },
                          '已刪除留言',
                        );
                    }}
                  >
                    刪除
                  </button>
                )}
              </div>
            )}
          </article>
        );
      })}
    </>
  );
}

type Data = { polls: Poll[]; comments: Comment[]; days: Day[]; places: Place[] };

function DecisionsView({ tripId, section, userId, isOwner, refresh, onChange, setError }: Props) {
  const [data, setData] = useState<Data | null>(null);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState('');
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setLocalError] = useState('');
  const inFlight = useRef(false);
  const source = '/trips/' + tripId;
  useEffect(() => {
    let active = true;
    const load =
      section === 'comments'
        ? api<Comment[]>(source + '/comments').then((comments) => ({
            comments,
            polls: [],
            places: [],
            days: [],
          }))
        : Promise.all([
            api<Poll[]>(source + '/polls'),
            api<Day[]>(source + '/days'),
            api<Place[]>(source + '/places'),
          ]).then(([polls, days, places]) => ({ polls, days, places, comments: [] }));
    load
      .then((result) => {
        if (active) {
          setData(result);
          setLocalError('');
        }
      })
      .catch((e) => {
        if (active) setLocalError(e instanceof Error ? e.message : '讀取資料失敗');
      });
    return () => {
      active = false;
    };
  }, [source, section, refresh, revision]);
  useEffect(() => {
    const deadlines =
      data?.polls.flatMap((p) => {
        const r = p.rounds[0];
        return !r.closed && r.deadline ? [new Date(r.deadline).getTime()] : [];
      }) ?? [];
    if (!deadlines.length) return;
    const delay = Math.max(1000, Math.min(...deadlines) - Date.now() + 100);
    const timer = setTimeout(() => setRevision((n) => n + 1), Math.min(delay, 2147483647));
    return () => clearTimeout(timer);
  }, [data]);
  const save: Save = async (url, method, body, message) => {
    if (inFlight.current) return false;
    inFlight.current = true;
    setBusy(true);
    setNotice('');
    try {
      await api(url, method, body);
      setNotice(message);
      setRevision((n) => n + 1);
      onChange();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失敗，請重試。');
      setRevision((n) => n + 1);
      return false;
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };
  return (
    <section className="dc-root" aria-busy={busy}>
      {error && (
        <p role="alert" className="dc-alert">
          {error} <button onClick={() => setRevision((n) => n + 1)}>重試</button>
        </p>
      )}
      {notice && (
        <p className="dc-feedback" role="status">
          <Check size={16} />
          {notice}
        </p>
      )}
      {!data && !error && <p role="status">載入中…</p>}
      {data && (
        <fieldset className="dc-layout" disabled={busy}>
          <legend className="dc-sr">{section === 'polls' ? '旅程投票' : '旅程討論'}</legend>
          {section === 'comments' ? (
            <Discussion
              comments={data.comments}
              tripId={tripId}
              userId={userId}
              isOwner={isOwner}
              save={save}
            />
          ) : (
            <>
              <div className="dc-heading">
                <h2>旅程投票</h2>
                {!creating && (
                  <button className="dc-primary" onClick={() => setCreating(true)}>
                    <Plus size={16} /> 發起投票
                  </button>
                )}
              </div>
              {creating && (
                <CreatePoll
                  tripId={tripId}
                  places={data.places}
                  save={save}
                  cancel={() => setCreating(false)}
                />
              )}
              {!data.polls.length && !creating && (
                <div className="dc-empty">
                  <Vote size={32} />
                  <h3>還沒有投票</h3>
                  <p>發起景點或日期投票，邀旅伴一起決定。</p>
                </div>
              )}
              {data.polls.map((p) => (
                <PollCard key={p.id} poll={p} userId={userId} days={data.days} save={save} />
              ))}
            </>
          )}
        </fieldset>
      )}
    </section>
  );
}

export default function Decisions(props: Props) {
  return <DecisionsView key={[props.tripId, props.userId, props.section].join('/')} {...props} />;
}
