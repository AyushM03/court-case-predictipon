// Types mirror the Pydantic models in src/court_delay/api.py.

export interface Court {
  court_id: string;
  court_name: string;
  district: string;
  judge_position: string;
  categories: string[];
}

export interface CaseCategory {
  id: string;
  label: string;
  criminal: boolean;
}

export interface Meta {
  districts: { district: string; courts: Court[] }[];
  case_categories: CaseCategory[];
  snapshot_date: string;
  horizon_days: number;
  trained_on: string;
  note: string;
}

export interface Contribution {
  feature: string;
  label: string;
  value: string;
  multiplier: number;
}

export interface Prediction {
  court: Court;
  case_category: string;
  case_category_label: string;
  congestion: { inflow_1y: number; backlog_2y: number; queue_ratio: number; clearance_1y: number | null };
  median_days: number | null;
  quartile_days: (number | null)[];
  decided_by: Record<"1y" | "2y" | "3y" | "5y", number>;
  curve: { day: number; decided: number }[];
  explanation: Contribution[];
  comparison: {
    courts_hearing_category: number;
    statewide_median_days: number | null;
    share_of_courts_slower: number;
  };
  warnings: string[];
  snapshot_date: string;
  note: string;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export function fetchMeta(signal?: AbortSignal): Promise<Meta> {
  return fetch("/api/meta", { signal }).then((r) => json<Meta>(r));
}

export function fetchPrediction(courtId: string, category: string, signal?: AbortSignal): Promise<Prediction> {
  return fetch("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ court_id: courtId, case_category: category }),
    signal,
  }).then((r) => json<Prediction>(r));
}
