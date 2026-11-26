'use client';

import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import {
  ArrowDown,
  ArrowUp,
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
import type { Member } from '../lib/trips';
import { uploadFiles, type FileInfo } from './Attachments';
import type { Place } from './plannerTypes';
import './decisions.css';

type Option = { id: string; text: string; place_id: string | null };
const modeLabels = { single: '單選', multiple: '多選', rating: '評分', ranked: '排序' };
type Mode = keyof typeof modeLabels;
const modeOptions = Object.entries(modeLabels).map(([value, name]) => (
  <option key={value} value={value}>
    {name}
  </option>
));
const scoringNotes = {
  rating: '每個選項評 1 到 5 分，總分最高者勝出。新增選項在補評前得 0 分。',
  ranked:
    '將所有選項依喜好排序。第一名得選項總數的分數，每下一名少 1 分。新增選項在補排前得 0 分，總分最高者勝出。',
};
type Result = {
  counts: Record<string, number>;
  winners: string[];
  ballots: {
    user_id: string;
    nickname: string;
    option_ids: string[];
    ratings: Record<string, number>;
  }[];
};
type Round = {
  id: string;
  number: number;
  title: string;
  kind: 'date' | 'place';
  mode: Mode;
  closed: boolean;
  deadline: string | null;
  options: Option[];
  my_choices: string[];
  my_ratings: Record<string, number>;
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
  attachments?: Pick<FileInfo, 'id' | 'filename'>[];
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
type Props = {
  tripId: string;
  members: Member[];
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
  const scored = round.mode === 'ranked' || round.mode === 'rating';
  const maxScore = round.mode === 'rating' ? 5 : round.mode === 'ranked' ? round.options.length : 1;
  return (
    <div className="dc-results">
      <p className="dc-result-title">
        {results.winners.length > 1 ? '平票' : '勝出選項'} ·{' '}
        {results.winners.map(nameOf).join('、')}
      </p>
      {round.options.map((o) => (
        <div className="dc-result-line" key={o.id}>
          <span>{o.text}</span>
          <b>
            {results.counts[o.id]} {scored ? '分' : '票'}
          </b>
          <progress
            aria-label={o.text + (scored ? ' 總分' : ' 得票')}
            max={results.ballots.length * maxScore}
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
              <strong>{b.nickname}</strong>　
              {b.option_ids
                .map((id, index) =>
                  round.mode === 'rating'
                    ? nameOf(id) + ' ' + b.ratings[id] + ' 分'
                    : round.mode === 'ranked'
                      ? index + 1 + '. ' + nameOf(id)
                      : nameOf(id),
                )
                .join('、')}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

const optionLength = 150;

function labelKey(label: string) {
  // Fold each code point independently: Python casefold expands letters (ẞ/ß → ss)
  // and treats sigma the same inside a word or at its end.
  const folded = Array.from(label, (char) => char.toLowerCase().toUpperCase().toLowerCase()).join(
    '',
  );
  return folded.replace(/^[\s\u0085]+|[\s\u0085]+$/gu, '').normalize('NFKC');
}

function repeatedLabels(labels: string[]) {
  const seen = new Set<string>();
  const repeated = new Set<string>();
  for (const label of labels) {
    const key = labelKey(label);
    if (seen.has(key)) repeated.add(key);
    seen.add(key);
  }
  return repeated;
}

function fitOption(text: string, suffix = '') {
  // HTML maxlength counts UTF-16 units. Keep the entire suffix and any final emoji intact.
  return (
    text
      .slice(0, optionLength - suffix.length)
      .replace(/[\uD800-\uDBFF]$/u, '')
      .trimEnd() + suffix
  );
}

function pollCandidates(places: Place[]) {
  const eligible = places.filter((place) => place.candidate);
  const namesakes = repeatedLabels(eligible.map((place) => place.name));
  const choices = eligible.map(({ id, name, address, city }) => {
    const description = [name, address?.trim() || city?.trim()].filter(Boolean).join(' · ');
    const label = fitOption(namesakes.has(labelKey(name)) ? description : name);
    return { id, description, label };
  });
  const repeatedDescriptions = repeatedLabels(choices.map((place) => place.description));
  const repeatedOptions = repeatedLabels(choices.map((place) => place.label));
  const reserved = new Set(
    choices.flatMap(({ description, label }) => [labelKey(description), labelKey(label)]),
  );
  return choices.map((choice) => {
    if (
      !repeatedDescriptions.has(labelKey(choice.description)) &&
      !repeatedOptions.has(labelKey(choice.label))
    )
      return choice;
    // This short place ID stays the same when the user changes selection order.
    // Reserve ordinary labels too, so a place named like a generated label still works.
    for (let attempt = 1; ; attempt++) {
      const marker = '（#' + choice.id.slice(0, 8) + (attempt === 1 ? '' : '-' + attempt) + '）';
      const description = choice.description + marker;
      const label = fitOption(choice.label, marker);
      if (reserved.has(labelKey(description)) || reserved.has(labelKey(label))) continue;
      reserved.add(labelKey(description));
      reserved.add(labelKey(label));
      return { id: choice.id, description, label };
    }
  });
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
  const [customOptions, setCustomOptions] = useState('');
  const [selectedPlaces, setSelectedPlaces] = useState<{ id: string; label: string }[]>([]);
  const candidates = useMemo(() => pollCandidates(places), [places]);

  function selectPlace(id: string) {
    const place = candidates.find((p) => p.id === id);
    if (place && !selectedPlaces.some((p) => p.id === id)) {
      setSelectedPlaces([...selectedPlaces, { id, label: place.label }]);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    const data = formData(event);
    const deadline = String(data.get('deadline') || '');
    const entries = customOptions
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
        options: [
          ...selectedPlaces.map((place) => ({
            text: String(data.get('place-' + place.id)).trim(),
            place_id: place.id,
          })),
          ...entries.map((text) => ({ text })),
        ],
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
              setCustomOptions('');
              setSelectedPlaces([]);
            }}
          >
            <option value="place">景點投票</option>
            <option value="date">日期投票</option>
          </select>
        </label>
        <label>
          選票方式
          <select name="mode">{modeOptions}</select>
        </label>
      </div>
      {kind === 'place' && candidates.length > 0 && (
        <label>
          從景點清單加入
          <select value="" onChange={(event) => selectPlace(event.target.value)}>
            <option value="">選擇景點</option>
            {candidates.map((place) => (
              <option
                key={place.id}
                value={place.id}
                disabled={selectedPlaces.some((selected) => selected.id === place.id)}
              >
                {place.description}
              </option>
            ))}
          </select>
        </label>
      )}
      {selectedPlaces.map((place) => (
        <div className="dc-inline" key={place.id}>
          <label className="dc-grow">
            {place.label} 的選項名稱
            <input
              name={'place-' + place.id}
              defaultValue={place.label}
              maxLength={optionLength}
              required
            />
          </label>
          <button
            type="button"
            aria-label={'移除選項 ' + place.label}
            onClick={() => setSelectedPlaces(selectedPlaces.filter((p) => p.id !== place.id))}
          >
            移除
          </button>
        </div>
      ))}
      <label>
        {kind === 'place'
          ? '手動輸入選項（每行一個，合計至少兩個選項）'
          : '候選選項（每行一個，至少兩個）'}
        <textarea
          rows={3}
          required={selectedPlaces.length === 0}
          value={customOptions}
          onChange={(e) => setCustomOptions(e.target.value)}
          placeholder={
            kind === 'date' ? '2027-04-03 ~ 2027-04-05\n2027-04-10 ~ 2027-04-12' : '輸入景點名稱'
          }
        />
      </label>
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

function RankedChoices({ round }: { round: Round }) {
  const [order, setOrder] = useState(round.my_choices);
  const ids = [...order, ...round.options.map((o) => o.id).filter((id) => !order.includes(id))];
  function move(from: number, to: number) {
    const next = [...ids];
    [next[from], next[to]] = [next[to], next[from]];
    setOrder(next);
  }
  return (
    <ol className="dc-ranked">
      {ids.map((id, index) => {
        const text = round.options.find((o) => o.id === id)?.text;
        return (
          <li key={id}>
            <input type="hidden" name="choice" value={id} />
            <span>
              {index + 1}. {text}
            </span>
            <button
              type="button"
              aria-label={'將' + text + '往前移'}
              disabled={index === 0}
              onClick={() => move(index, index - 1)}
            >
              <ArrowUp size={16} />
            </button>
            <button
              type="button"
              aria-label={'將' + text + '往後移'}
              disabled={index === ids.length - 1}
              onClick={() => move(index, index + 1)}
            >
              <ArrowDown size={16} />
            </button>
          </li>
        );
      })}
    </ol>
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
      {
        version,
        ballot_version: round.ballot_version,
        ...(round.mode === 'rating'
          ? {
              ratings: Object.fromEntries(
                round.options.map((o) => [o.id, Number(data.get('rating-' + o.id))]),
              ),
            }
          : { option_ids: data.getAll('choice') }),
      },
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
          {modeLabels[round.mode]}
        </small>
      </div>
      <h3>{round.title}</h3>
      {(round.mode === 'rating' || round.mode === 'ranked') && (
        <p className="dc-note">{scoringNotes[round.mode]}</p>
      )}
      {round.deadline && <small>截止於 {localTime(round.deadline)}</small>}
      {round.review_needed && (
        <p role="status" className="dc-alert">
          旅伴新增了選項，請重新檢視並儲存你的選票。
        </p>
      )}
      {!round.closed && (
        <form key={round.id + '-' + round.ballot_version} onSubmit={submitVote}>
          {round.mode === 'ranked' ? (
            <RankedChoices round={round} />
          ) : round.mode === 'rating' ? (
            <div className="dc-choices">
              {round.options.map((o) => (
                <label className="dc-rating" key={o.id}>
                  {o.text}
                  <select
                    name={'rating-' + o.id}
                    required
                    defaultValue={round.my_ratings[o.id] ?? ''}
                  >
                    <option value="">選擇分數</option>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option value={n} key={n}>
                        {n} 分
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          ) : (
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
          )}
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
                {modeOptions}
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
  members,
  userId,
  isOwner,
  tripId,
  save,
}: {
  comments: Comment[];
  members: Member[];
  userId: string;
  isOwner: boolean;
  tripId: string;
  save: Save;
}) {
  const [target, setTarget] = useState<{ comment: Comment; type: 'edit' | 'reply' } | null>(null);
  const [draft, setDraft] = useState('');
  const [images, setImages] = useState<Pick<FileInfo, 'id' | 'filename'>[]>([]);
  const [selected, setSelected] = useState<File[]>([]);
  const [sending, setSending] = useState(false);
  const [imageError, setImageError] = useState('');
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const id = location.hash.match(/^#comment-([a-f0-9-]{36})$/i)?.[1];
    if (id) document.getElementById('comment-' + id)?.focus();
  }, []);
  function renderMentions(content: string) {
    return content.replace(
      /@\[([^\]\n]{1,100})\]\(([\da-f-]{36})\)/gi,
      (_, name, id) => '@' + (members.find((m) => m.id === id)?.nickname ?? name),
    );
  }
  function addMention(id: string) {
    const member = members.find((m) => m.id === id);
    if (!member || !input.current) return;
    const start = input.current.selectionStart;
    const end = input.current.selectionEnd;
    const token =
      '@[' + member.nickname.replaceAll(']', '］').replace(/[\r\n]/g, ' ') + '](' + id + ') ';
    const next = draft.slice(0, start) + token + draft.slice(end);
    if (next.length > 5000) return;
    setDraft(next);
    requestAnimationFrame(() => {
      input.current?.focus();
      input.current?.setSelectionRange(start + token.length, start + token.length);
    });
  }
  function start(comment: Comment, type: 'edit' | 'reply') {
    setTarget({ comment, type });
    setImages(type === 'edit' ? comment.attachments || [] : []);
    setSelected([]);
    setImageError('');
    setDraft(type === 'edit' ? comment.content : '');
    input.current?.focus();
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (sending) return;
    setSending(true);
    setImageError('');
    try {
      let attached = images;
      if (selected.length) {
        const form = new FormData();
        selected.forEach((image) => form.append('files', image));
        form.set('category', '留言圖片');
        form.set('kind', 'draft');
        form.set('target_id', userId);
        attached = [...images, ...(await uploadFiles(tripId, form))];
        setImages(attached);
        setSelected([]);
      }
      const attachment_ids = attached.map((image) => image.id);
      const ok =
        target?.type === 'edit'
          ? await save(
              '/comments/' + target.comment.id,
              'PATCH',
              { content, attachment_ids, version: target.comment.version },
              '已更新留言',
            )
          : await save(
              '/trips/' + tripId + '/comments',
              'POST',
              { content, attachment_ids, parent_id: target?.comment.id },
              '已送出留言',
            );
      if (ok) {
        setTarget(null);
        setDraft('');
        setImages([]);
      }
    } catch (e) {
      setImageError(e instanceof Error ? e.message : '圖片上傳失敗。');
    } finally {
      setSending(false);
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
        <label>
          留言圖片
          <input
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp,image/gif"
            disabled={sending}
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              if (files.length + images.length + selected.length > 10) {
                setImageError('每則留言最多 10 張圖片。');
              } else {
                setSelected([...selected, ...files]);
                setImageError('');
              }
              e.target.value = '';
            }}
          />
        </label>
        {images.map((img) => (
          <button
            type="button"
            disabled={sending}
            key={img.id}
            onClick={() => setImages(images.filter((i) => i.id !== img.id))}
          >
            移除 {img.filename}
          </button>
        ))}
        {selected.map((file, index) => (
          <button
            type="button"
            disabled={sending}
            key={index}
            onClick={() => setSelected(selected.filter((_, i) => i !== index))}
          >
            移除 {file.name}
          </button>
        ))}
        {imageError && <p role="alert">{imageError}</p>}
        {members.some((m) => m.id !== userId) && (
          <label>
            提及旅伴
            <select value="" onChange={(event) => addMention(event.target.value)}>
              <option value="">選擇 @旅伴</option>
              {members
                .filter((m) => m.id !== userId)
                .map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nickname}
                    {members.some((other) => other.id !== m.id && other.nickname === m.nickname)
                      ? ' · ' + m.id.slice(0, 8)
                      : ''}
                  </option>
                ))}
            </select>
          </label>
        )}
        <div className="dc-actions">
          <button className="dc-primary" disabled={!draft.trim() || sending}>
            <Send size={15} /> {target?.type === 'edit' ? '儲存修改' : '送出留言'}
          </button>
          {target && (
            <button
              type="button"
              onClick={() => {
                setTarget(null);
                setDraft('');
                setImages([]);
                setSelected([]);
                setImageError('');
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
          <article className="dc-panel dc-comment" key={c.id} id={'comment-' + c.id} tabIndex={-1}>
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
                回覆 {parent.nickname} ·{' '}
                {parent.deleted ? '留言已刪除' : renderMentions(parent.content)}
              </blockquote>
            )}
            <p>{c.deleted ? '此留言已刪除' : renderMentions(c.content)}</p>
            {!c.deleted &&
              c.attachments?.map((img) => (
                <a key={img.id} href={'/api/v1/files/' + img.id + '/download'} download>
                  <img
                    className="af-comment-image"
                    alt={img.filename}
                    src={'/api/v1/files/' + img.id + '/preview'}
                    loading="lazy"
                  />
                </a>
              ))}
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

function DecisionsView({
  tripId,
  section,
  userId,
  isOwner,
  members,
  refresh,
  onChange,
  setError,
}: Props) {
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
              members={members}
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
