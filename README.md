# Zinab Lab · Ethiopia Climate Explorer

A NASA Space Apps Challenge project exploring how Earth observation and climate data can support local climate resilience in Ethiopia.

## Run locally

```sh
npm install
npm run dev
```

For a production Node server:

```sh
npm run build
npm run start
```

The Node adapter is required for the live climate API; a static-only host cannot serve this endpoint.

## Dashboard

The responsive dashboard includes four selectable Ethiopian observation points, year selection, a monthly precipitation chart, summary metrics, an interactive [OpenStreetMap](https://www.openstreetmap.org/) map, a location directory, and individual profiles at `/locations/`. The `/analytics/` page compares experimental projections for all four points and maps a month-selectable spatial interpolation. The app requests monthly precipitation (`PRECTOTCORR`) from the [NASA POWER API](https://power.larc.nasa.gov/docs/services/api/temporal/monthly/).

Browser pages request `/api/climate/{locationId}?start={year}&end={year}` and `/api/analytics?start={year}&end={year}` from the Astro Node backend. The backend validates point IDs and year ranges, retrieves and validates NASA POWER observations, and caches successful responses and analytics results in memory. Dashboard and profile numbers remain unavailable when the API cannot provide source data; synthetic fallback values are not displayed.

The experimental analytics model is a TensorFlow.js multivariate linear regression trained with Adam gradient descent. It uses five complete years of monthly NASA POWER observations at the four configured stations, with year, seasonal, coordinate, and interaction features, to estimate the next year's monthly rates. The displayed RMSE is in-sample and is not an independent skill score. The map uses inverse-distance interpolation of those station projections and is restricted to their convex hull. With only four stations, this is a sparse-data research visualization—not validated countrywide coverage, a weather or seasonal forecast, or a product with uncertainty bounds. Projections are shown only when the complete observed history is available.

Precipitation is displayed as a monthly mean daily rate in mm/day, matching the NASA POWER parameter units. Seasonal notes are general regional context, not forecasts or planting advice.

## Stack

- Astro
- TensorFlow.js for gradient-trained exploratory regression
- Leaflet for the interactive spatial interpolation map
- NASA POWER monthly point API
- Vanilla JavaScript for dashboard controls and data visualization
