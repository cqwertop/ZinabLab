import type { APIRoute } from 'astro';
import { locations } from '../../../data/locations';
import { fetchClimateHistory } from '../../../lib/server/climate-provider';

export const prerender = false;

function jsonResponse(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Cache-Control': status === 200 ? 'public, max-age=300, stale-while-revalidate=900' : 'no-store',
      'Content-Type': 'application/json; charset=utf-8',
    },
  });
}

export const GET: APIRoute = async ({ params, url }) => {
  const location = locations.find((point) => point.id === params.id);
  if (!location) return jsonResponse({ error: 'Unknown observation point.' }, 404);

  const startYear = Number(url.searchParams.get('start'));
  const endYear = Number(url.searchParams.get('end'));
  const latestCompleteYear = new Date().getUTCFullYear() - 1;
  if (
    !Number.isInteger(startYear) ||
    !Number.isInteger(endYear) ||
    startYear < 1981 ||
    endYear > latestCompleteYear ||
    startYear > endYear ||
    endYear - startYear > 9
  ) {
    return jsonResponse({ error: `Choose a complete year range between 1981 and ${latestCompleteYear} (up to 10 years).` }, 400);
  }

  try {
    return jsonResponse(await fetchClimateHistory(location, startYear, endYear));
  } catch (error) {
    console.error(`Climate API request failed for ${location.id}:`, error);
    const message = error instanceof Error ? error.message : 'Unexpected upstream error.';
    return jsonResponse({ error: message }, 502);
  }
};
