export const locations = [
  { id: 'addis', name: 'Central Highlands', lat: 9.03, lon: 38.74, label: 'Addis Ababa', description: 'Highland plateau and capital region.' },
  { id: 'mekele', name: 'Northern Highlands', lat: 13.5, lon: 39.47, label: 'Mekelle', description: 'Northern highlands and Tigray region.' },
  { id: 'hawassa', name: 'Southern Rift Valley', lat: 7.06, lon: 38.48, label: 'Hawassa', description: 'Southern Rift Valley and Sidama region.' },
  { id: 'gambela', name: 'Western Lowlands', lat: 8.25, lon: 34.59, label: 'Gambela', description: 'Warm western lowlands near the Baro River.' },
] as const;

export type ObservationLocation = (typeof locations)[number];

export const latestCompleteYear = new Date().getUTCFullYear() - 1;
export const historyYears = Array.from({ length: 5 }, (_, index) => latestCompleteYear - 4 + index);
