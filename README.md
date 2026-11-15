# Zinab Lab · Ethiopia Climate Explorer

A NASA Space Apps Challenge project exploring how Earth observation and climate data can support local climate resilience in Ethiopia.

## Run locally

```sh
npm install
npm run dev
```

## Dashboard

The Astro homepage includes a responsive climate dashboard with four selectable Ethiopian observation points, year selection, a monthly precipitation chart, summary metrics, and an interactive schematic location map. It requests monthly precipitation (`PRECTOTCORR`) from the [NASA POWER API](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/). The API request uses the selected point and year. If the request fails or the data is unavailable, the dashboard clearly labels its illustrative fallback values; these sample values are not measured observations or forecasts.

Precipitation is displayed as a monthly mean daily rate in mm/day, matching the NASA POWER parameter units. Seasonal notes are general regional context, not forecasts or planting advice.

## Stack

- Astro
- NASA POWER monthly point API
- Vanilla JavaScript for dashboard controls and data visualization
