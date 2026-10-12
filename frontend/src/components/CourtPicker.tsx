import type { Meta } from "../api";

export interface Selection {
  district: string;
  courtId: string;
  category: string;
}

interface Props {
  meta: Meta;
  value: Selection;
  onChange: (next: Selection) => void;
}

/** District → court → case type. Case types the court hears come first; the rest are grouped
 *  under "rarely heard here" (the API returns a warning for those). */
export function CourtPicker({ meta, value, onChange }: Props) {
  const courts = meta.districts.find((d) => d.district === value.district)?.courts ?? [];
  const court = courts.find((c) => c.court_id === value.courtId);
  const heard = new Set(court?.categories ?? []);
  const label = (id: string) => meta.case_categories.find((c) => c.id === id)?.label ?? id;
  const others = meta.case_categories.filter((c) => !heard.has(c.id) && c.id !== "nan");

  function pickDistrict(district: string) {
    const first = meta.districts.find((d) => d.district === district)!.courts[0];
    onChange({ district, courtId: first.court_id, category: keepCategory(first.categories) });
  }
  function pickCourt(courtId: string) {
    const c = courts.find((x) => x.court_id === courtId)!;
    onChange({ ...value, courtId, category: keepCategory(c.categories) });
  }
  const keepCategory = (cats: string[]) => (cats.includes(value.category) ? value.category : cats[0]);

  return (
    <form className="controls" onSubmit={(e) => e.preventDefault()}>
      <label>
        District
        <select value={value.district} onChange={(e) => pickDistrict(e.target.value)}>
          {meta.districts.map((d) => (
            <option key={d.district} value={d.district}>
              {d.district}
            </option>
          ))}
        </select>
      </label>
      <label>
        Court
        <select value={value.courtId} onChange={(e) => pickCourt(e.target.value)}>
          {courts.map((c) => (
            <option key={c.court_id} value={c.court_id}>
              {c.court_name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Case type
        <select value={value.category} onChange={(e) => onChange({ ...value, category: e.target.value })}>
          <optgroup label="Heard in this court">
            {court?.categories.map((id) => (
              <option key={id} value={id}>
                {label(id)}
              </option>
            ))}
          </optgroup>
          <optgroup label="Rarely heard here">
            {others.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
    </form>
  );
}
