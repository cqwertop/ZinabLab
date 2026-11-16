export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export const DRY = ['#ffb38f', '#ff8a5c', '#f2552e', '#c2361a'];
export const WET = ['#9ad8ff', '#5cbcff', '#2f95f0', '#1c6cd0'];
export const NEUTRAL = '#76718a';
export const RESTING = '#4a4363';

export function pctColor(pct: number | null | undefined) {
  if (pct === null || pct === undefined || Number.isNaN(pct)) return RESTING;
  if (pct < 40) return DRY[3];
  if (pct < 60) return DRY[2];
  if (pct < 80) return DRY[1];
  if (pct < 95) return DRY[0];
  if (pct <= 105) return NEUTRAL;
  if (pct <= 125) return WET[0];
  if (pct <= 150) return WET[1];
  if (pct <= 200) return WET[2];
  return WET[3];
}

export function zColor(z: number) {
  if (z < -1.5) return DRY[3];
  if (z < -1) return DRY[2];
  if (z < -0.5) return DRY[1];
  if (z < -0.25) return DRY[0];
  if (z <= 0.25) return NEUTRAL;
  if (z <= 0.5) return WET[0];
  if (z <= 1) return WET[1];
  if (z <= 1.5) return WET[2];
  return WET[3];
}

export function statusColor(status: string, pct: number | null) {
  return status === 'seasonal-dry' ? RESTING : pctColor(pct);
}

export const STATUS_ICON: Record<string, string> = {
  'seasonal-dry': 'moon',
  'severe-deficit': 'crack',
  deficit: 'sun',
  'near-normal': 'cloud',
  wet: 'storm',
  unknown: 'eye',
};

export function pct(v: number | null | undefined, digits = 0) {
  return v === null || v === undefined ? '—' : `${v.toFixed(digits)}%`;
}

export function mm(v: number | null | undefined, digits = 0) {
  return v === null || v === undefined ? '—' : `${v.toFixed(digits)} mm`;
}

export function signed(v: number | null | undefined, digits = 1) {
  if (v === null || v === undefined) return '—';
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(digits)}`;
}

export function niceDate(iso: string | null | undefined) {
  if (!iso) return '—';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

export function monthLabel(ym: string) {
  const [y, m] = ym.split('-').map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

export function esc(s: unknown) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);
}

export function icon(name: string, cls = '') {
  return `<svg class="zi ${cls}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
}

export function plainPct(pctValue: number | null) {
  if (pctValue === null) return 'no reading';
  if (pctValue < 50) return 'less than half the usual rain';
  if (pctValue < 75) return 'about two-thirds of the usual rain';
  if (pctValue < 95) return 'a little less rain than usual';
  if (pctValue <= 105) return 'about the usual amount of rain';
  if (pctValue <= 150) return 'more rain than usual';
  return 'far more rain than usual';
}
