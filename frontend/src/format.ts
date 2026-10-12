/** "12 days", "7 months", "1.6 years"; null means beyond the prediction horizon. */
export function formatDuration(days: number | null, horizonDays = 1825): string {
  if (days === null) return `over ${Math.round(horizonDays / 365)} years`;
  if (days < 60) return `${Math.round(days)} day${Math.round(days) === 1 ? "" : "s"}`;
  if (days < 365) return `${Math.round(days / 30.44)} months`;
  return `${(days / 365).toFixed(1)} years`;
}

export function percent(p: number, digits = 0): string {
  return `${(p * 100).toFixed(digits)}%`;
}

export function years(day: number): string {
  return day < 365 ? `${Math.round(day / 30.44)} months` : `${(day / 365).toFixed(1)} years`;
}

/** How the court ranks among courts hearing the same case type, as a short phrase. */
export function rankPhrase(shareSlower: number): { head: string; tail: string } {
  if (shareSlower >= 0.5) return { head: `Faster than ${percent(shareSlower)}`, tail: "of courts" };
  return { head: `Slower than ${percent(1 - shareSlower)}`, tail: "of courts" };
}
