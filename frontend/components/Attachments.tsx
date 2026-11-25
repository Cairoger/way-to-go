'use client';
import { useEffect, useState, type FormEvent } from 'react';
import { Download, Eye, Paperclip, Upload, RotateCcw } from 'lucide-react';
import { api } from '../lib/api';
import { errorText, type Member } from '../lib/trips';
import { Modal } from './ui/dialog';
import { Button } from './ui/button';
import './attachments.css';

type Kind = 'trip' | 'item' | 'task' | 'expense' | 'booking' | 'comment' | 'draft';
export type FileInfo = {
  id: string;
  filename: string;
  mime: string;
  size: number;
  category: string;
  editable: boolean;
  private: boolean;
  reader_ids: string[];
  version: number;
  removed: boolean;
  links: { kind: Kind; target_id: string }[];
};
type Target = { tripId: string; kind?: Kind; targetId?: string };
type Props = Target & {
  refresh?: number;
  userId?: string;
  members?: Member[];
  onChange?: () => void;
};
const accept = '.png,.jpg,.jpeg,.gif,.webp,.pdf,.docx,.xlsx,.pptx';
const labels: Record<Kind, string> = {
  trip: '旅程',
  item: '行程',
  task: '任務',
  expense: '費用',
  booking: '預訂',
  comment: '留言',
  draft: '待送出留言',
};
const sizes = (n: number) =>
  n >= 1024 ** 2 ? (n / 1024 ** 2).toFixed(1) + ' MiB' : Math.max(1, Math.ceil(n / 1024)) + ' KiB';

export async function uploadFiles(tripId: string, form: FormData): Promise<FileInfo[]> {
  const response = await fetch('/api/v1/trips/' + tripId + '/files', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-Requested-With': 'WayToGo' },
    body: form,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      data?.message ??
        (response.status === 413 ? '檔案超過上傳容量限制。' : '上傳未完成，請重試。'),
    );
  return data;
}

function Editor({
  file,
  tripId,
  kind,
  targetId,
  members,
  limit,
  close,
  saved,
}: Props & { file?: FileInfo; limit: number; close(): void; saved(): void }) {
  const [priv, setPriv] = useState(file?.private ?? false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [people, setPeople] = useState(members ?? []);
  useEffect(() => {
    let live = true;
    if (!members)
      api<Member[]>('/trips/' + tripId + '/members')
        .then((data) => {
          if (live) setPeople(data);
        })
        .catch((e) => {
          if (live) setError(errorText(e));
        });
    return () => {
      live = false;
    };
  }, [tripId, members]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    try {
      if (file) {
        await api('/files/' + file.id, 'PATCH', {
          version: file.version,
          private: priv,
          category: form.get('category'),
          reader_ids: form.getAll('reader_ids'),
        });
      } else {
        const files = form.getAll('files') as File[];
        if (!files.length || files.length > 10 || files.some((f) => f.size > limit || !f.size))
          throw new Error('請選擇 1–10 個非空白檔案，每檔最多 ' + sizes(limit) + '。');
        form.set('kind', kind || 'trip');
        form.set('target_id', targetId || tripId);
        form.set('private', String(priv));
        await uploadFiles(tripId, form);
      }
      saved();
      close();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={file ? '管理附件' : '上傳附件'} onClose={close}>
      <form className="stack" onSubmit={submit}>
        {file ? (
          <p>{file.filename}</p>
        ) : (
          <label className="field">
            選擇檔案
            <input required name="files" type="file" accept={accept} multiple />
            <small>
              圖片、PDF、Word、Excel、PowerPoint，每檔最多 {sizes(limit)}，可一次選 10 個。
            </small>
          </label>
        )}
        <label className="field">
          分類
          <input required name="category" maxLength={64} defaultValue={file?.category || '其他'} />
        </label>
        <label className="field">
          可見範圍
          <select
            value={priv ? 'private' : 'shared'}
            onChange={(e) => setPriv(e.target.value === 'private')}
          >
            <option value="shared">與可查看關聯項目的旅伴共用</option>
            <option value="private">僅自己及指定旅伴</option>
          </select>
        </label>
        {kind === 'booking' && <small>預訂附件僅限建立預訂的旅伴和該筆預訂的旅客。</small>}
        {priv && (
          <fieldset>
            <legend>授權旅伴</legend>
            <div className="af-readers">
              {people.map((p) => (
                <label key={p.id}>
                  <input
                    type="checkbox"
                    name="reader_ids"
                    value={p.id}
                    defaultChecked={file?.reader_ids.includes(p.id)}
                  />
                  {p.nickname}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        {error && (
          <p role="alert" className="error-inline">
            {error}
          </p>
        )}
        <div className="form-actions">
          <Button variant="outline" onClick={close}>
            取消
          </Button>
          <Button type="submit" disabled={busy}>
            {busy ? '處理中…' : file ? '儲存附件設定' : '上傳檔案'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function Preview({ file, close }: { file: FileInfo; close(): void }) {
  const [text, setText] = useState('讀取預覽中…');
  const url = '/api/v1/files/' + file.id + '/preview';
  const image = file.mime.startsWith('image/');
  useEffect(() => {
    let live = true;
    if (!image)
      fetch(url, { cache: 'no-store', credentials: 'same-origin' })
        .then(async (r) => {
          if (!r.ok) throw Error('無法預覽，請確認附件權限。');
          return r.text();
        })
        .then((t) => {
          if (live) setText(t);
        })
        .catch((e) => {
          if (live) setText(errorText(e));
        });
    return () => {
      live = false;
    };
  }, [url, image]);
  return (
    <Modal title={'預覽 · ' + file.filename} onClose={close}>
      {image ? (
        <img className="af-preview" src={url} alt={file.filename} />
      ) : (
        <pre className="af-text">{text}</pre>
      )}
      <a className="text-btn" href={'/api/v1/files/' + file.id + '/download'} download>
        下載原始檔案
      </a>
    </Modal>
  );
}

export function AttachmentLibrary(props: Props) {
  const { tripId, kind, targetId, refresh = 0, onChange } = props;
  const [rows, setRows] = useState<FileInfo[]>([]),
    [loaded, setLoaded] = useState(false),
    [error, setError] = useState('');
  const [limit, setLimit] = useState(10485760),
    [recycle, setRecycle] = useState(false),
    [revision, setRevision] = useState(0);
  const [category, setCategory] = useState(''),
    [editing, setEditing] = useState<FileInfo | 'new' | null>(null),
    [preview, setPreview] = useState<FileInfo | null>(null);
  const [pending, setPending] = useState(false);
  useEffect(() => {
    let live = true;
    api<{ file_max_bytes: number }>('/trips/' + tripId + '/files/limits')
      .then((x) => {
        if (live) setLimit(x.file_max_bytes);
      })
      .catch((e) => {
        if (live) setError(errorText(e));
      });
    return () => {
      live = false;
    };
  }, [tripId]);
  useEffect(() => {
    let live = true;
    const q = new URLSearchParams({ recycled: String(recycle) });
    if (kind) {
      q.set('kind', kind);
      q.set('target_id', targetId || tripId);
    }
    api<FileInfo[]>('/trips/' + tripId + '/files?' + q)
      .then((x) => {
        if (live) {
          setRows(x);
          setLoaded(true);
          setError('');
        }
      })
      .catch((e) => {
        if (live) {
          setRows([]);
          setError(errorText(e));
        }
      });
    return () => {
      live = false;
    };
  }, [tripId, kind, targetId, refresh, revision, recycle]);
  function changed() {
    setRevision((v) => v + 1);
    onChange?.();
  }
  async function lifecycle(f: FileInfo) {
    if (!f.removed && !confirm('將「' + f.filename + '」移到回收區？')) return;
    setPending(true);
    try {
      await api('/files/' + f.id + (f.removed ? '/restore' : ''), f.removed ? 'POST' : 'DELETE', {
        version: f.version,
      });
      changed();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setPending(false);
    }
  }
  const filtered = rows.filter((f) => !category || f.category === category);
  return (
    <section className="af-library">
      <div className="af-heading">
        <h2>
          <Paperclip size={20} />
          {kind ? '關聯附件' : '旅程文件'}
        </h2>
        {!recycle && (
          <Button onClick={() => setEditing('new')}>
            <Upload size={16} />
            上傳附件
          </Button>
        )}
      </div>
      <div className="af-toolbar">
        <Button
          variant="outline"
          onClick={() => {
            setCategory('');
            setRecycle(!recycle);
          }}
        >
          {recycle ? '返回文件' : '我的回收區'}
        </Button>
        <label>
          分類{' '}
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">全部</option>
            {Array.from(new Set(rows.map((f) => f.category))).map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      {error && (
        <p role="alert" className="error-inline">
          {error}
        </p>
      )}
      {!error && !loaded && <p role="status">載入文件中…</p>}
      {!error && loaded && !filtered.length && (
        <p className="af-empty">
          {recycle ? '回收區沒有符合條件的文件。' : '目前沒有可檢視的附件。'}
        </p>
      )}
      <ul className="af-list">
        {filtered.map((f) => (
          <li key={f.id}>
            <div>
              <strong>{f.filename}</strong>
              <small>
                {f.category} · {sizes(f.size)} · {f.private ? '指定旅伴' : '共用'} ·{' '}
                {Array.from(new Set(f.links.map((l) => labels[l.kind]))).join('、')}
              </small>
            </div>
            {f.removed ? (
              <Button variant="outline" disabled={pending} onClick={() => void lifecycle(f)}>
                <RotateCcw size={14} />
                復原
              </Button>
            ) : (
              <div className="af-actions">
                <button type="button" onClick={() => setPreview(f)}>
                  <Eye size={14} />
                  預覽
                </button>
                <a href={'/api/v1/files/' + f.id + '/download'} download>
                  <Download size={14} />
                  下載
                </a>
                {f.editable && (
                  <>
                    <button type="button" onClick={() => setEditing(f)}>
                      管理
                    </button>
                    <button type="button" disabled={pending} onClick={() => void lifecycle(f)}>
                      移到回收區
                    </button>
                  </>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
      {editing && (
        <Editor
          {...props}
          file={editing === 'new' ? undefined : editing}
          limit={limit}
          close={() => setEditing(null)}
          saved={changed}
        />
      )}
      {preview && <Preview file={preview} close={() => setPreview(null)} />}
    </section>
  );
}
export default AttachmentLibrary;
export function AttachmentButton(props: Target) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="af-link" onClick={() => setOpen(true)}>
        <Paperclip size={14} />
        附件
      </button>
      {open && (
        <Modal title="附件" onClose={() => setOpen(false)}>
          <AttachmentLibrary {...props} />
        </Modal>
      )}
    </>
  );
}
