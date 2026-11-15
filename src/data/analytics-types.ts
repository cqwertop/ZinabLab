export interface LocationProjection {
  id: string;
  name: string;
  label: string;
  latitude: number;
  longitude: number;
  monthlyValues: number[];
  projectedMean: number;
  baselineMean: number;
  changePercent: number;
}

export interface RainfallCell {
  latitude: number;
  longitude: number;
  monthlyValues: number[];
}

export interface RainfallAnalytics {
  source: 'NASA POWER';
  parameter: 'PRECTOTCORR';
  unit: 'mm/day';
  model: {
    name: string;
    method: string;
    historyStart: number;
    historyEnd: number;
    targetYear: number;
    epochs: number;
    sampleCount: number;
    trainingRmse: number;
    features: string[];
  };
  locations: LocationProjection[];
  surface: {
    cellLatitudeStep: number;
    cellLongitudeStep: number;
    coveragePolygon: Array<{ latitude: number; longitude: number }>;
    cells: RainfallCell[];
  };
}
