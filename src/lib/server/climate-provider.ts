import type { ObservationLocation } from '../../data/locations';
import type { MonthlyHistory } from '../climate-analytics';

export interface ClimateHistoryResponse {
  source: 'NASA POWER';
  parameter: 'PRECTOTCORR';
  unit: 'mm/day';
  location: {
    id: string;
    name: string;
    label: string;
    latitude: number;
    longitude: number;
  };
  history: MonthlyHistory;
}

const cache = new Map<string, { expiresAt: number; data: ClimateHistoryResponse }>();
const cacheDurationMs = 6 * 60 * 60 * 1000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export async function fetchClimateHistory(
  location: ObservationLocation,
  startYear: number,
  endYear: number,
): Promise<ClimateHistoryResponse> {
  const cacheKey = `${location.id}:${startYear}:${endYear}`;
  const cached = cache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) return cached.data;

  const params = new URLSearchParams({
    parameters: 'PRECTOTCORR',
    community: 'AG',
    longitude: String(location.lon),
    latitude: String(location.lat),
    start: String(startYear),
    end: String(endYear),
    format: 'JSON',
  });
  const response = await fetch(`https://power.larc.nasa.gov/api/temporal/monthly/point?${params}`, {
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`NASA POWER responded with HTTP ${response.status}.`);

  const payload: unknown = await response.json();
  if (!isRecord(payload) || !isRecord(payload.properties) || !isRecord(payload.properties.parameter)) {
    throw new Error('NASA POWER returned an invalid monthly precipitation response.');
  }
  const monthlyData = payload.properties.parameter.PRECTOTCORR;
  if (!isRecord(monthlyData)) throw new Error('NASA POWER response is missing PRECTOTCORR values.');

  const history: MonthlyHistory = {};
  for (let year = startYear; year <= endYear; year += 1) {
    const values = Array.from({ length: 12 }, (_, month) => {
      const value = monthlyData[`${year}${String(month + 1).padStart(2, '0')}`];
      return typeof value === 'number' ? value : Number.NaN;
    });
    if (!values.every((value) => Number.isFinite(value) && value >= 0)) {
      throw new Error(`NASA POWER has incomplete precipitation values for ${year}.`);
    }
    history[year] = values;
  }

  const data: ClimateHistoryResponse = {
    source: 'NASA POWER',
    parameter: 'PRECTOTCORR',
    unit: 'mm/day',
    location: {
      id: location.id,
      name: location.name,
      label: location.label,
      latitude: location.lat,
      longitude: location.lon,
    },
    history,
  };
  cache.set(cacheKey, { expiresAt: Date.now() + cacheDurationMs, data });
  return data;
}
