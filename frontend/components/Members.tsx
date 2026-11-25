'use client';
import { useEffect, useRef, useState } from 'react';
import { Copy, Link2, UserRound, Users, ShieldCheck, Mail } from 'lucide-react';
import { api, ApiError } from '../lib/api';
import { type Trip, type Member, errorText } from '../lib/trips';
import { Button } from './ui/button';
type Invite = {
  id: string;
  expires_at: string;
  revoked_at?: string | null;
  code?: string;
  url?: string;
  qr_data_url?: string;
};
export default function Members({
  trip,
  userId,
  members,
  online,
  onChange,
  onExit,
  setError,
}: {
  trip: Trip;
  userId: string;
  members: Member[];
  online: string[];
  onChange: () => void;
  onExit: () => void;
  setError: (s: string) => void;
}) {
  const owner = trip.owner_id === userId;
  const [invites, setInvites] = useState<Invite[]>([]),
    [issued, setIssued] = useState<Invite | null>(null),
    [days, setDays] = useState(7),
    [pending, setPending] = useState(false),
    [notice, setNotice] = useState('');
  const path = '/trips/' + trip.id;
  const inviteAttempt = useRef<{ key: string; days: number } | null>(null);
  useEffect(() => {
    let live = true;
    if (owner)
      api<Invite[]>(path + '/invitations')
        .then((a) => {
          if (live) setInvites(a);
        })
        .catch((e) => {
          if (live) setError(errorText(e));
        });
    return () => {
      live = false;
    };
  }, [path, owner, setError]);
  async function run(fn: () => Promise<void>) {
    setPending(true);
    setNotice('');
    try {
      await fn();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setPending(false);
    }
  }
  async function revoke(i: Invite) {
    if (!window.confirm('撤銷此邀請？已加入的旅伴會保有權限。')) return;
    await run(async () => {
      await api(path + '/invitations/' + i.id, 'DELETE');
      if (issued?.id === i.id) setIssued(null);
      setInvites(await api(path + '/invitations'));
      setNotice('邀請已撤銷。');
    });
  }
  return (
    <div className="members-section">
      <h2 className="section-title">
        <Users />
        旅程成員 <small>{members.length}</small>
      </h2>
      <div className="card member-list">
        {trip.creator_name && (
          <p className="muted">
            旅程建立者　{trip.creator_name} ·{' '}
            {new Date(trip.created_at).toLocaleDateString('zh-TW')}
          </p>
        )}
        {members.map((m) => (
          <div key={m.id} className="member-row">
            <span className="avatar">
              <UserRound size={16} />
            </span>
            <div>
              <b>
                {m.nickname}
                {m.id === userId ? '（你）' : ''}
              </b>
              <small>
                {m.role === 'owner' ? '旅程擁有者' : '旅伴'}
                {online.includes(m.id) ? ' · 在線' : ''}
              </small>
            </div>
            {owner && m.id !== userId && (
              <div className="member-actions">
                <button
                  disabled={pending}
                  onClick={() => {
                    if (window.confirm('將旅程所有權轉移給 ' + m.nickname + '？'))
                      void run(async () => {
                        await api(path + '/transfer', 'POST', {
                          version: trip.version,
                          user_id: m.id,
                        });
                        setIssued(null);
                        onChange();
                      });
                  }}
                >
                  轉移所有權
                </button>
                <button
                  disabled={pending}
                  onClick={() => {
                    if (window.confirm('移除 ' + m.nickname + '？其資料管理權將轉移給擁有者。'))
                      void run(async () => {
                        await api(path + '/members/' + m.id, 'DELETE');
                        onChange();
                      });
                  }}
                >
                  移除
                </button>
              </div>
            )}
            {m.role === 'owner' && <ShieldCheck className="push-right" size={18} />}
          </div>
        ))}
      </div>
      {!owner && (
        <Button
          variant="outline"
          disabled={pending}
          onClick={() => {
            if (window.confirm('確定退出此旅程？'))
              void run(async () => {
                await api(path + '/members/' + userId, 'DELETE');
                onExit();
              });
          }}
        >
          退出旅程
        </Button>
      )}
      {owner && (
        <>
          <h2 className="section-title">
            <Link2 />
            邀請旅伴
          </h2>
          <div className="card padded stack">
            <div className="inline-form">
              <label className="field">
                邀請期限
                <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
                  {[1, 3, 7, 14, 30].map((n) => (
                    <option value={n} key={n}>
                      {n} 天
                    </option>
                  ))}
                </select>
              </label>
              <Button
                disabled={pending}
                onClick={() =>
                  run(async () => {
                    if (!inviteAttempt.current || inviteAttempt.current.days !== days)
                      inviteAttempt.current = { key: crypto.randomUUID(), days };
                    let i: Invite;
                    try {
                      i = await api<Invite>(
                        path + '/invitations',
                        'POST',
                        { days },
                        inviteAttempt.current.key,
                      );
                    } catch (error) {
                      if (error instanceof ApiError && [403, 409, 410, 422].includes(error.status))
                        inviteAttempt.current = null;
                      throw error;
                    }
                    inviteAttempt.current = null;
                    setIssued(i);
                    setInvites((all) => [i, ...all.filter((previous) => previous.id !== i.id)]);
                  })
                }
              >
                產生邀請
              </Button>
            </div>
            {issued && (
              <div className="issued-invite">
                {issued.qr_data_url && (
                  <img width="132" height="132" src={issued.qr_data_url} alt="旅程邀請 QR Code" />
                )}
                <div>
                  <p>邀請碼</p>
                  <strong>{issued.code}</strong>
                  <input aria-label="邀請連結" readOnly value={issued.url ?? ''} />
                  <Button
                    variant="outline"
                    onClick={() =>
                      run(async () => {
                        await navigator.clipboard.writeText(issued.url!);
                        setNotice('已複製邀請連結。');
                      })
                    }
                  >
                    <Copy size={15} />
                    複製連結
                  </Button>
                  {issued.url && (
                    <a
                      className="text-btn"
                      href={
                        'mailto:?subject=' +
                        encodeURIComponent('一起規劃「' + trip.title + '」') +
                        '&body=' +
                        encodeURIComponent(
                          '邀請你加入「' +
                            trip.title +
                            '」。\n\n開啟邀請連結：' +
                            issued.url +
                            '\n邀請碼：' +
                            issued.code,
                        )
                      }
                    >
                      <Mail size={15} />用 Email 邀請
                    </a>
                  )}
                </div>
              </div>
            )}
            {invites
              .filter((i) => !i.revoked_at && new Date(i.expires_at) > new Date())
              .map((i) => (
                <div className="invite-row" key={i.id}>
                  <span>有效至 {new Date(i.expires_at).toLocaleString('zh-TW')}</span>
                  <button disabled={pending} onClick={() => revoke(i)}>
                    撤銷
                  </button>
                </div>
              ))}
          </div>
        </>
      )}
      <p role="status">{notice}</p>
    </div>
  );
}
