import type { APIRoute } from 'astro';
import type { RainfallAnalytics } from '../../data/analytics-types';
import { latestCompleteYear, locations } from '../../data/locations';
import { fetchClimateHistory } from '../../lib/server/climate-provider';
import { buildRainfallAnalytics } from '../../lib/server/rainfall-model';

export const prerender = false;

const cacheDurationMs = 6 * 60 * 60 * 1000;
const cache = new Map<string, { expiresAt: number; data: RainfallAnalytics }>();
const inFlight = new Map<string, Promise<RainfallAnalytics>>();

function jsonResponse(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Cache-Control': status === 200 ? 'public, max-age=300, stale-while-revalidate=900' : 'no-store',
      'Content-Type': 'application/json; charset=utf-8',
    },
  });
}

export const GET: APIRoute = async ({ url }) => {
  const startYear = Number(url.searchParams.get('start'));
  const endYear = Number(url.searchParams.get('end'));
  if (
    !Number.isInteger(startYear) ||
    !Number.isInteger(endYear) ||
    startYear < 1981 ||
    endYear > latestCompleteYear ||
    startYear > endYear ||
    endYear - startYear < 2 ||
    endYear - startYear > 9
  ) {
    return jsonResponse({ error: `Choose at least three complete years, ending no later than ${latestCompleteYear}.` }, 400);
  }

  const cacheKey = `${startYear}:${endYear}`;
  const cached = cache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now()) return jsonResponse(cached.data);

  let pending = inFlight.get(cacheKey);
  if (!pending) {
    pending = Promise.all(locations.map(async (location) => {
      const climate = await fetchClimateHistory(location, startYear, endYear);
      return { location, history: climate.history };
    })).then((histories) => buildRainfallAnalytics(histories, startYear, endYear));
    inFlight.set(cacheKey, pending);
  }

  try {
    const data = await pending;
    cache.set(cacheKey, { expiresAt: Date.now() + cacheDurationMs, data });
    return jsonResponse(data);
  } catch (error) {
    console.error('Rainfall analytics model request failed:', error);
    const message = error instanceof Error ? error.message : 'Unexpected model error.';
    return jsonResponse({ error: message }, 502);
  } finally {
    if (inFlight.get(cacheKey) === pending) inFlight.delete(cacheKey);
  }
};
