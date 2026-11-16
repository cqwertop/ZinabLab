const BASE = (import.meta.env.PUBLIC_API_BASE ?? '').replace(/\/$/, '');

export class BridgeError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

const memo = new Map<string, Promise<unknown>>();

async function request<T>(path: string, init?: RequestInit, timeoutMs = 90000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE}/api${path}`, { ...init, signal: controller.signal, headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) } });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = body.detail ?? detail;
      } catch {}
      throw new BridgeError(detail, response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof BridgeError) throw error;
    if ((error as Error).name === 'AbortError') throw new BridgeError('The rain server took too long to answer.');
    throw new BridgeError('Cannot reach the Zinab Python server. Start it with: cd backend && .venv\\Scripts\\python -m uvicorn main:app --port 8000');
  } finally {
    clearTimeout(timer);
  }
}

function cached<T>(path: string): Promise<T> {
  if (!memo.has(path)) {
    const p = request<T>(path).catch((e) => {
      memo.delete(path);
      throw e;
    });
    memo.set(path, p);
  }
  return memo.get(path) as Promise<T>;
}

export type Window = { days: number; rain: number; normal: number; pct: number | null };
export type Season = { name: string; months: number[]; role: string };
export type StatusLite = {
  id: string;
  name: string;
  status: 'seasonal-dry' | 'severe-deficit' | 'deficit' | 'near-normal' | 'wet' | 'unknown';
  label: string;
  lastObserved: string;
  windows: { d30: Window; d60: Window; d90: Window };
  drySpellDays: number;
  heat: { t30: number | null; normal: number | null; anomaly: number | null };
  soil: { wetness: number | null; normal: number | null; anomaly: number | null };
  season: { month: number; inSeason: boolean; nextRainyMonth: number | null; seasons: Season[] };
  next16?: { totalRain: number; wetDays: number; waterBalance: number } | null;
};
export type Driver = { index: string; month: string; value: number; phase: string; trend: number; history: { month: string; value: number }[]; source: string; url: string };
export type Pulse = {
  generatedAt: string;
  today: string;
  lastObserved: string;
  national: { rain60: number; normal60: number; pct60: number | null; rain30: number; normal30: number; pct30: number | null; deficitAreaPct: number; regionsInDeficit: number; regionsInSeason: number };
  ranking: StatusLite[];
  regions: StatusLite[];
  drivers: { enso: Driver; iod: Driver } | null;
};
export type RegionSummary = {
  id: string;
  name: string;
  group: string;
  rainyMonths: number[];
  seasons: Season[];
  livelihood: string;
  sentinel: { name: string; note: string };
  anchor: { lat: number; lon: number };
  samplePoints: { lat: number; lon: number }[];
};
export type RegionsPayload = { regions: RegionSummary[]; geojson: GeoJSON.FeatureCollection; outline: GeoJSON.Feature };
export type OutlookMonth = {
  month: string;
  monthName: string;
  lead: number;
  drySeason: boolean;
  expectedMm: number;
  normalMm: number;
  rangeMm: [number, number];
  pctOfNormal: number | null;
  zScore: number;
  probabilities: { below: number; near: number; above: number };
  lean: 'dry' | 'wet' | 'neutral';
  drivers: { feature: string; effect: number }[];
};
export type Factor = { key: string; title: string; verdict: 'primary' | 'contributing' | 'evidence' | 'context' | 'counter'; detail: string; source: string };
export type Article = { title: string; url: string; source: string; date: string | null; image: string | null; causes: string[] };
export type News = { provider: string; query: string; articles: Article[]; signals: { cause: string; mentions: number }[] };
export type RegionDetail = {
  region: RegionSummary;
  status: StatusLite & {
    longestDrySpell90: number;
    climatology: { month: number; mmPerDay: number; mm: number }[];
    series: { date: string; rain: number; normalDaily: number; cumRain: number; cumNormal: number }[];
    source: string;
  };
  history: { monthly: { month: string; rain: number; normal: number; z: number }[]; climatology: { month: number; mean: number; p10: number; p90: number }[]; years: { year: number; rain: number; pct: number }[] };
  outlook: { issuedFrom: string; months: OutlookMonth[]; error?: string };
  next16: { days: { date: string; rain: number | null; chance: number | null; tmax: number | null; et0: number | null }[]; totalRain: number; totalEt0: number; waterBalance: number; wetDays: number } | null;
  nowcast: { month: string; monthName: string; observedMm: number; observedThrough: string; forecastMm: number; forecastDays: number; climatologyMm: number; projectedMm: number; normalMm: number; pctOfNormal: number | null } | null;
  why: { headline: string; confidence: 'high' | 'medium' | 'low'; factors: Factor[] };
  fieldKit: { audience: string; icon: string; title: string; text: string }[];
  news: News | null;
};
export type Grid = { source: string; cellSize: number; cells: { id: string; lon: number; lat: number }[]; months: string[]; z: number[][]; mm: number[][] };
export type National = { source: string; monthly: { month: string; rain: number; normal: number; anomaly: number; z: number }[]; seasonal: { year: number; season: string; rain: number; normal: number; pct: number; z: number }[] };
export type Skill = {
  method: string;
  trainingData: string;
  predictors: string[];
  validation: string;
  leads: { lead: number; samples: number; correlation: number; msss: number; rpss: number; hitRate: number; chirpsCorrelation: number | null; chirpsPairs: number; strongEnsoCorrelation: number | null; sigma: number }[];
  coefficients: Record<string, { feature: string; weight: number }[]>;
};
export type SarPass = { scene: string; platform: string; time: string; direction: string; mode: string; polarization: string; orbit: number; browse: string | null; footprint: GeoJSON.Polygon | null };
export type Sar = { source: string; searchUrl: string; passes: SarPass[] };
export type ChatTurn = { role: 'user' | 'assistant'; content: string };
export type ChatReply = { reply: string; tools: string[]; mode: 'claude' | 'offline'; focusRegion: string | null; note?: string };

export const bridge = {
  regions: () => cached<RegionsPayload>('/regions'),
  pulse: () => cached<Pulse>('/pulse'),
  region: (id: string) => cached<RegionDetail>(`/regions/${id}`),
  sar: (id: string) => cached<Sar>(`/regions/${id}/sar`),
  grid: () => cached<Grid>('/history/grid'),
  national: () => cached<National>('/history/national'),
  model: () => cached<Skill>('/model'),
  suggestions: () => cached<{ suggestions: string[]; mode: string }>('/chat/suggestions'),
  chat: (messages: ChatTurn[]) => request<ChatReply>('/chat', { method: 'POST', body: JSON.stringify({ messages }) }, 180000),
};
