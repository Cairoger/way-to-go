import type { Member, Trip } from '../lib/trips';
export type PrepProps = {
  trip: Trip;
  userId: string;
  members: Member[];
  refresh: number;
  onChange: () => void;
  setError: (s: string) => void;
};
export type DayRef = { id: string; day_number: number; items: { id: string; title: string }[] };
export function ItemOptions({ days, linkedId }: { days: DayRef[]; linkedId?: string | null }) {
  return (
    <>
      <option value="">無關聯活動</option>
      {linkedId && !days.some((d) => d.items.some((i) => i.id === linkedId)) && (
        <option value={linkedId}>已移除的活動（保留關聯）</option>
      )}
      {days.map((d) => (
        <optgroup key={d.id} label={'Day ' + d.day_number}>
          {d.items.map((i) => (
            <option value={i.id} key={i.id}>
              {i.title}
            </option>
          ))}
        </optgroup>
      ))}
    </>
  );
}
