import * as tf from '@tensorflow/tfjs';
import type { RainfallAnalytics, LocationProjection } from '../../data/analytics-types';
import { locations, type ObservationLocation } from '../../data/locations';
import type { ClimateHistoryResponse } from './climate-provider';

const epochs = 800;
const targetScale = 10;
const featureNames = [
  'normalized year',
  'normalized latitude',
  'normalized longitude',
  'annual sine seasonality',
  'annual cosine seasonality',
  'year × seasonal sine',
  'year × seasonal cosine',
  'latitude × seasonal sine',
  'latitude × seasonal cosine',
  'longitude × seasonal sine',
  'longitude × seasonal cosine',
];

interface TrainingPoint {
  location: ObservationLocation;
  history: ClimateHistoryResponse['history'];
}

interface GeoPoint {
  latitude: number;
  longitude: number;
}

function createFeatures(
  location: ObservationLocation,
  year: number,
  month: number,
  startYear: number,
  endYear: number,
): number[] {
  const yearSpan = Math.max(1, endYear - startYear);
  const time = (year - startYear) / yearSpan;
  const latitude = (location.lat - 10) / 5;
  const longitude = (location.lon - 37) / 5;
  const angle = (2 * Math.PI * month) / 12;
  const seasonalSine = Math.sin(angle);
  const seasonalCosine = Math.cos(angle);

  return [
    time,
    latitude,
    longitude,
    seasonalSine,
    seasonalCosine,
    time * seasonalSine,
    time * seasonalCosine,
    latitude * seasonalSine,
    latitude * seasonalCosine,
    longitude * seasonalSine,
    longitude * seasonalCosine,
  ];
}

function cross(origin: GeoPoint, first: GeoPoint, second: GeoPoint): number {
  return (first.longitude - origin.longitude) * (second.latitude - origin.latitude)
    - (first.latitude - origin.latitude) * (second.longitude - origin.longitude);
}

function convexHull(points: GeoPoint[]): GeoPoint[] {
  const sorted = [...points].sort((a, b) => a.longitude - b.longitude || a.latitude - b.latitude);
  const lower: GeoPoint[] = [];
  for (const point of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) lower.pop();
    lower.push(point);
  }

  const upper: GeoPoint[] = [];
  for (const point of sorted.reverse()) {
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) upper.pop();
    upper.push(point);
  }
  lower.pop();
  upper.pop();
  return lower.concat(upper);
}

function isInsidePolygon(point: GeoPoint, polygon: GeoPoint[]): boolean {
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index, index += 1) {
    const currentPoint = polygon[index];
    const previousPoint = polygon[previous];
    const crossesLatitude = (currentPoint.latitude > point.latitude) !== (previousPoint.latitude > point.latitude);
    const longitudeAtLatitude = ((previousPoint.longitude - currentPoint.longitude)
      * (point.latitude - currentPoint.latitude))
      / (previousPoint.latitude - currentPoint.latitude)
      + currentPoint.longitude;
    if (crossesLatitude && point.longitude < longitudeAtLatitude) inside = !inside;
  }
  return inside;
}

function interpolateMonthlyValues(point: GeoPoint, projections: LocationProjection[]): number[] {
  const weightedValues = Array(12).fill(0) as number[];
  let totalWeight = 0;

  for (const projection of projections) {
    const latitudeDistance = (point.latitude - projection.latitude) * 111.32;
    const longitudeDistance = (point.longitude - projection.longitude)
      * 111.32
      * Math.cos(((point.latitude + projection.latitude) / 2) * Math.PI / 180);
    const distanceSquared = latitudeDistance ** 2 + longitudeDistance ** 2;
    if (distanceSquared < 1e-8) return projection.monthlyValues;
    const weight = 1 / distanceSquared;
    totalWeight += weight;
    projection.monthlyValues.forEach((value, month) => {
      weightedValues[month] += value * weight;
    });
  }

  return weightedValues.map((value) => value / totalWeight);
}

export async function buildRainfallAnalytics(
  histories: TrainingPoint[],
  startYear: number,
  endYear: number,
): Promise<RainfallAnalytics> {
  await tf.setBackend('cpu');
  await tf.ready();

  const trainingFeatures: number[][] = [];
  const trainingValues: number[] = [];
  for (const { location, history } of histories) {
    for (let year = startYear; year <= endYear; year += 1) {
      for (let month = 0; month < 12; month += 1) {
        trainingFeatures.push(createFeatures(location, year, month, startYear, endYear));
        trainingValues.push(history[year][month] / targetScale);
      }
    }
  }
  if (trainingFeatures.length < 36) throw new Error('Insufficient observations to train the rainfall model.');

  const featuresTensor = tf.tensor2d(trainingFeatures);
  const valuesTensor = tf.tensor2d(trainingValues.map((value) => [value]));
  const weights = tf.variable(tf.zeros([featureNames.length, 1]));
  const bias = tf.variable(tf.scalar(0));
  const optimizer = tf.train.adam(0.03);
  let trainingRmse = Number.NaN;

  try {
    for (let epoch = 0; epoch < epochs; epoch += 1) {
      const loss = optimizer.minimize(() => tf.tidy(() => {
        const residuals = featuresTensor.matMul(weights).add(bias).sub(valuesTensor);
        const fitError = residuals.square().mean();
        const penalty = weights.square().sum().mul(0.0001);
        return fitError.add(penalty);
      }), true, [weights, bias]);
      if (!loss) throw new Error('TensorFlow.js did not produce a training loss.');
      const lossValue = loss.dataSync()[0];
      loss.dispose();
      if (!Number.isFinite(lossValue)) throw new Error('Rainfall model training produced a non-finite loss.');
    }

    trainingRmse = tf.tidy(() => featuresTensor
      .matMul(weights)
      .add(bias)
      .sub(valuesTensor)
      .square()
      .mean()
      .sqrt()
      .mul(targetScale)
      .dataSync()[0]);

    const targetYear = endYear + 1;
    const forecastFeatures = histories.flatMap(({ location }) =>
      Array.from({ length: 12 }, (_, month) => createFeatures(location, targetYear, month, startYear, endYear)),
    );
    const forecastTensor = tf.tensor2d(forecastFeatures);
    const normalizedPredictions = forecastTensor.matMul(weights).add(bias).dataSync();
    forecastTensor.dispose();

    const projections: LocationProjection[] = histories.map(({ location, history }, locationIndex) => {
      const monthlyValues = Array.from({ length: 12 }, (_, month) =>
        Math.max(0, normalizedPredictions[locationIndex * 12 + month] * targetScale),
      );
      const baselineMean = Array.from({ length: endYear - startYear + 1 }, (_, index) => {
        const values = history[startYear + index];
        return values.reduce((sum, value) => sum + value, 0) / values.length;
      }).reduce((sum, value) => sum + value, 0) / (endYear - startYear + 1);
      const projectedMean = monthlyValues.reduce((sum, value) => sum + value, 0) / 12;

      return {
        id: location.id,
        name: location.name,
        label: location.label,
        latitude: location.lat,
        longitude: location.lon,
        monthlyValues,
        projectedMean,
        baselineMean,
        changePercent: baselineMean === 0 ? 0 : ((projectedMean - baselineMean) / baselineMean) * 100,
      };
    });

    const points = locations.map(({ lat, lon }) => ({ latitude: lat, longitude: lon }));
    const coveragePolygon = convexHull(points);
    const minLatitude = Math.min(...coveragePolygon.map((point) => point.latitude));
    const maxLatitude = Math.max(...coveragePolygon.map((point) => point.latitude));
    const minLongitude = Math.min(...coveragePolygon.map((point) => point.longitude));
    const maxLongitude = Math.max(...coveragePolygon.map((point) => point.longitude));
    const rowCount = 21;
    const columnCount = 21;
    const cellLatitudeStep = (maxLatitude - minLatitude) / rowCount;
    const cellLongitudeStep = (maxLongitude - minLongitude) / columnCount;
    const cells = [];

    for (let row = 0; row < rowCount; row += 1) {
      for (let column = 0; column < columnCount; column += 1) {
        const point = {
          latitude: minLatitude + (row + 0.5) * cellLatitudeStep,
          longitude: minLongitude + (column + 0.5) * cellLongitudeStep,
        };
        if (isInsidePolygon(point, coveragePolygon)) {
          cells.push({
            ...point,
            monthlyValues: interpolateMonthlyValues(point, projections),
          });
        }
      }
    }

    return {
      source: 'NASA POWER',
      parameter: 'PRECTOTCORR',
      unit: 'mm/day',
      model: {
        name: 'TensorFlow.js seasonal-spatial regression',
        method: 'Multivariate linear regression with seasonal and coordinate interactions, trained with Adam gradient descent; spatial cells use inverse-distance interpolation inside the station convex hull.',
        historyStart: startYear,
        historyEnd: endYear,
        targetYear,
        epochs,
        sampleCount: trainingFeatures.length,
        trainingRmse,
        features: featureNames,
      },
      locations: projections,
      surface: {
        cellLatitudeStep,
        cellLongitudeStep,
        coveragePolygon,
        cells,
      },
    };
  } finally {
    featuresTensor.dispose();
    valuesTensor.dispose();
    weights.dispose();
    bias.dispose();
    optimizer.dispose();
  }
}
