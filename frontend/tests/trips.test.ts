import { describe, it, expect } from 'vitest';
import { formatDates, matchingTrips } from '../lib/trips';
import { samples } from '../lib/samples';
describe('旅程列表', () => {
  const records = samples.map((s) => s.trip);
  it('顯示未定日期與跨年度行程', () => {
    expect(formatDates(null, null)).toBe('日期待定');
    expect(formatDates('2026-12-30', '2027-01-02')).toBe('2026.12.30 – 2027.01.02');
  });
  it('依目的地及狀態篩選', () => {
    expect(matchingTrips(records, 'home', 'confirmed', '義大利')).toEqual([records[1]]);
  });
  it('封存、完成與回收分開', () => {
    const archived = { ...records[2], archived: true };
    const deleted = { ...records[1], deleted_at: '2026-11-01' };
    const all = [records[0], archived, deleted];
    expect(matchingTrips(all, 'home', 'all', '')).toEqual([records[0]]);
    expect(matchingTrips(all, 'archive', 'completed', '')).toEqual([archived]);
    expect(matchingTrips(all, 'trash', 'all', '')).toEqual([deleted]);
  });
});
