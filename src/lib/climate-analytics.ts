import type { RainfallAnalytics } from '../data/analytics-types';
import type { ObservationLocation } from '../data/locations';

export type MonthlyHistory = Record<number, number[]>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function errorFromPayload(payload: unknown, status: number): Error {
  return new Error(
    isRecord(payload) && typeof payload.error === 'string'
      ? payload.error
      : `Climate API responded with HTTP ${status}.`,
  );
}

function isMonthlyHistory(value: unknown, startYear: number, endYear: number): value is MonthlyHistory {
  if (!isRecord(value)) return false;
  for (let year = startYear; year <= endYear; year += 1) {
    const values = value[year];
    if (
      !Array.isArray(values) ||
      values.length !== 12 ||
      !values.every((item) => typeof item === 'number' && Number.isFinite(item) && item >= 0)
    ) return false;
  }
  return true;
}

function isLocationProjection(value: unknown): boolean {
  if (!isRecord(value) || typeof value.id !== 'string') return false;
  return typeof value.name === 'string'
    && typeof value.label === 'string'
    && typeof value.latitude === 'number'
    && Number.isFinite(value.latitude)
    && typeof value.longitude === 'number'
    && Number.isFinite(value.longitude)
    && typeof value.projectedMean === 'number'
    && Number.isFinite(value.projectedMean)
    && typeof value.baselineMean === 'number'
    && Number.isFinite(value.baselineMean)
    && typeof value.changePercent === 'number'
    && Number.isFinite(value.changePercent)
    && Array.isArray(value.monthlyValues)
    && value.monthlyValues.length === 12
    && value.monthlyValues.every((item) => typeof item === 'number' && Number.isFinite(item) && item >= 0);
}

function isRainfallAnalytics(value: unknown): value is RainfallAnalytics {
  if (!isRecord(value) || value.source !== 'NASA POWER' || value.parameter !== 'PRECTOTCORR' || value.unit !== 'mm/day') {
    return false;
  }
  const model = value.model;
  const surface = value.surface;
  if (!isRecord(model) || !isRecord(surface) || !Array.isArray(value.locations)) return false;

  const validModel = typeof model.name === 'string'
    && typeof model.method === 'string'
    && typeof model.historyStart === 'number'
    && typeof model.historyEnd === 'number'
    && typeof model.targetYear === 'number'
    && typeof model.epochs === 'number'
    && typeof model.sampleCount === 'number'
    && typeof model.trainingRmse === 'number'
    && Number.isFinite(model.trainingRmse)
    && Array.isArray(model.features)
    && model.features.every((feature) => typeof feature === 'string');
  const validPolygon = Array.isArray(surface.coveragePolygon)
    && surface.coveragePolygon.length >= 3
    && surface.coveragePolygon.every((point) =>
      isRecord(point)
      && typeof point.latitude === 'number'
      && Number.isFinite(point.latitude)
      && typeof point.longitude === 'number'
      && Number.isFinite(point.longitude),
    );
  const validCells = Array.isArray(surface.cells)
    && surface.cells.length > 0
    && surface.cells.every((cell) =>
      isRecord(cell)
      && typeof cell.latitude === 'number'
      && Number.isFinite(cell.latitude)
      && typeof cell.longitude === 'number'
      && Number.isFinite(cell.longitude)
      && Array.isArray(cell.monthlyValues)
      && cell.monthlyValues.length === 12
      && cell.monthlyValues.every((item) => typeof item === 'number' && Number.isFinite(item) && item >= 0),
    );
  return validModel
    && validPolygon
    && validCells
    && typeof surface.cellLatitudeStep === 'number'
    && Number.isFinite(surface.cellLatitudeStep)
    && typeof surface.cellLongitudeStep === 'number'
    && Number.isFinite(surface.cellLongitudeStep)
    && value.locations.every(isLocationProjection);
}

export async function fetchMonthlyHistory(
  location: ObservationLocation,
  startYear: number,
  endYear: number,
): Promise<MonthlyHistory> {
  const params = new URLSearchParams({ start: String(startYear), end: String(endYear) });
  const response = await fetch(`/api/climate/${encodeURIComponent(location.id)}?${params}`, {
    headers: { Accept: 'application/json' },
  });
  const payload: unknown = await response.json();
  if (!response.ok) throw errorFromPayload(payload, response.status);
  if (!isRecord(payload) || payload.source !== 'NASA POWER' || payload.parameter !== 'PRECTOTCORR' || payload.unit !== 'mm/day') {
    throw new Error('The climate API response has unexpected source or unit metadata.');
  }
  if (!isRecord(payload.location) || payload.location.id !== location.id) {
    throw new Error('The climate API response does not match the selected observation point.');
  }
  if (!isMonthlyHistory(payload.history, startYear, endYear)) {
    throw new Error('The climate API response has incomplete monthly precipitation values.');
  }
  if (endYear - startYear < 2) throw new Error('At least three complete years are required for trend analysis.');
  return payload.history;
}

export async function fetchRainfallAnalytics(startYear: number, endYear: number): Promise<RainfallAnalytics> {
  const params = new URLSearchParams({ start: String(startYear), end: String(endYear) });
  const response = await fetch(`/api/analytics?${params}`, {
    headers: { Accept: 'application/json' },
  });
  const payload: unknown = await response.json();
  if (!response.ok) throw errorFromPayload(payload, response.status);
  if (!isRainfallAnalytics(payload)) throw new Error('The analytics API returned an invalid model result.');
  return payload;
}
