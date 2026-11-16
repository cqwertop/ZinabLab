import asyncio
import calendar
import math
from dataclasses import dataclass

import numpy as np

from core.regions import MONTHS, Region, load_regions
from services import drivers, power
from services.chirps import regional_monthly

LEADS = (1, 2, 3)
WET_MONTH_MM = 20.0
TERCILE_Z = 0.4307
RIDGE_LAMBDA = 8.0
FEATURES = [
    ("z_last", "Last month's rain anomaly"),
    ("z_3mo", "3-month rain anomaly"),
    ("persist", "Same-season persistence"),
    ("oni", "ENSO (ONI)"),
    ("dmi", "Indian Ocean Dipole"),
    ("oni_kiremt_north", "El Niño vs. Kiremt (north)"),
    ("oni_kiremt_south", "El Niño vs. Kiremt (south)"),
    ("oni_ond_south", "ENSO vs. autumn rains (south)"),
    ("oni_mam_south", "ENSO vs. spring rains (south)"),
    ("dmi_ond_south", "IOD vs. autumn rains (south)"),
    ("dmi_kiremt_north", "IOD vs. Kiremt (north)"),
]


def add_months(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    total = y * 12 + (m - 1) + n
    return f"{total // 12}-{total % 12 + 1:02d}"


def days_in(ym: str) -> int:
    return calendar.monthrange(int(ym[:4]), int(ym[5:7]))[1]


def season_of(month: int) -> str:
    if month in (6, 7, 8, 9):
        return "kiremt"
    if month in (10, 11, 12):
        return "ond"
    if month in (3, 4, 5):
        return "mam"
    return "dry"


def latest_at_or_before(series: dict[str, float], ym: str):
    if ym in series:
        return series[ym]
    keys = [k for k in series if k <= ym]
    return series[max(keys)] if keys else 0.0


@dataclass
class RegionClimate:
    totals: dict[str, float]
    mean: dict[int, float]
    std: dict[int, float]

    def z(self, ym: str):
        value = self.totals.get(ym)
        if value is None:
            return None
        m = int(ym[5:7])
        if self.mean[m] < WET_MONTH_MM * 0.4 or self.std[m] <= 0:
            return 0.0
        return max(-3.0, min(3.0, (value - self.mean[m]) / self.std[m]))


def build_features(region: Region, clim: RegionClimate, issue: str, target: str, oni: dict, dmi: dict):
    z_last = clim.z(issue)
    if z_last is None:
        return None
    window = [clim.z(add_months(issue, -i)) for i in range(3)]
    window = [w for w in window if w is not None]
    z3 = sum(window) / len(window)
    tm = int(target[5:7])
    im = int(issue[5:7])
    t_season = season_of(tm)
    persist = z_last if season_of(im) == t_season and t_season != "dry" else 0.0
    o = latest_at_or_before(oni, add_months(issue, -1))
    d = latest_at_or_before(dmi, issue)
    north = 1.0 if region.group == "north" else 0.0
    south = 1.0 - north
    kir = 1.0 if t_season == "kiremt" else 0.0
    ond = 1.0 if t_season == "ond" else 0.0
    mam = 1.0 if t_season == "mam" else 0.0
    return [z_last, z3, persist, o, d, o * kir * north, o * kir * south, o * ond * south, o * mam * south, d * ond * south, d * kir * north]


class Ridge:
    def __init__(self, lam: float):
        self.lam = lam

    def fit(self, x: np.ndarray, y: np.ndarray, w: np.ndarray | None = None):
        self.mu = x.mean(axis=0)
        self.sd = x.std(axis=0)
        self.sd[self.sd == 0] = 1.0
        xs = (x - self.mu) / self.sd
        w = np.ones(len(y)) if w is None else w
        xw = xs * w[:, None]
        a = xs.T @ xw + self.lam * np.eye(xs.shape[1])
        self.coef = np.linalg.solve(a, xw.T @ y)
        self.bias = float(np.average(y - xs @ self.coef, weights=w))
        return self

    def contributions(self, x: np.ndarray):
        return ((x - self.mu) / self.sd) * self.coef

    def predict(self, x: np.ndarray):
        return ((x - self.mu) / self.sd) @ self.coef + self.bias


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def tercile_probs(mu: float, sigma: float):
    below = norm_cdf((-TERCILE_Z - mu) / sigma)
    above = 1 - norm_cdf((TERCILE_Z - mu) / sigma)
    return below, 1 - below - above, above


def rps(probs, observed_cat: int):
    cum_f = np.cumsum(probs)
    cum_o = np.cumsum([1.0 if i == observed_cat else 0.0 for i in range(3)])
    return float(np.sum((cum_f - cum_o) ** 2))


def category(z: float) -> int:
    return 0 if z < -TERCILE_Z else (2 if z > TERCILE_Z else 1)


class ForecastEngine:
    def __init__(self):
        self.ready = False
        self.lock = asyncio.Lock()
        self.models: dict[int, Ridge] = {}
        self.sigma: dict[int, float] = {}
        self.climates: dict[str, RegionClimate] = {}
        self.skill: dict = {}
        self.oni: dict = {}
        self.dmi: dict = {}

    async def ensure(self):
        if self.ready:
            return
        async with self.lock:
            if self.ready:
                return
            await self._train()
            self.ready = True

    async def _load_climates(self):
        regions = load_regions()
        histories = await asyncio.gather(*(power.gather_points(power.monthly_history, r.points) for r in regions))
        for region, point_series in zip(regions, histories):
            totals: dict[str, float] = {}
            keys = set().union(*(s.keys() for s in point_series))
            for key in sorted(keys):
                vals = [s.get(key) for s in point_series if s.get(key) is not None]
                if not vals:
                    continue
                ym = f"{key[:4]}-{key[4:6]}"
                totals[ym] = float(np.mean(vals)) * days_in(ym)
            mean, std = {}, {}
            for m in range(1, 13):
                vals = [v for k, v in totals.items() if int(k[5:7]) == m]
                mean[m] = float(np.mean(vals)) if vals else 0.0
                std[m] = float(np.std(vals, ddof=1)) if len(vals) > 2 else 0.0
            self.climates[region.id] = RegionClimate(totals, mean, std)

    def _samples(self, lead: int):
        rows, ys, meta = [], [], []
        for region in load_regions():
            clim = self.climates[region.id]
            for issue in sorted(clim.totals):
                target = add_months(issue, lead)
                if target not in clim.totals:
                    continue
                if clim.mean[int(target[5:7])] < WET_MONTH_MM:
                    continue
                feats = build_features(region, clim, issue, target, self.oni, self.dmi)
                y = clim.z(target)
                if feats is None or y is None:
                    continue
                rows.append(feats)
                ys.append(y)
                meta.append((region.id, issue, target))
        return np.array(rows), np.array(ys), meta

    async def _train(self):
        self.oni, self.dmi = await asyncio.gather(drivers.oni_series(), drivers.dmi_series())
        await self._load_climates()
        chirps = regional_monthly()
        chirps_z = {(r.region, r.month): r.z for r in chirps.itertuples()}
        skill = {}
        for lead in LEADS:
            x, y, meta = self._samples(lead)
            years = np.array([int(m[2][:4]) for m in meta])
            preds = np.zeros_like(y)
            for year in np.unique(years):
                train = years != year
                model = Ridge(RIDGE_LAMBDA).fit(x[train], y[train])
                preds[~train] = model.predict(x[~train])
            resid = y - preds
            sigma = float(np.sqrt(np.mean(resid**2)))
            mse_model = float(np.mean(resid**2))
            mse_clim = float(np.mean(y**2))
            rps_model = rps_clim = 0.0
            hits = 0
            for obs, mu in zip(y, preds):
                probs = tercile_probs(mu, sigma)
                cat = category(obs)
                rps_model += rps(probs, cat)
                rps_clim += rps((1 / 3, 1 / 3, 1 / 3), cat)
                hits += int(int(np.argmax(probs)) == cat)
            corr = float(np.corrcoef(y, preds)[0, 1])
            pairs = [(p, chirps_z[(m[0], m[2])]) for p, m in zip(preds, meta) if (m[0], m[2]) in chirps_z]
            chirps_corr = float(np.corrcoef([p for p, _ in pairs], [c for _, c in pairs])[0, 1]) if len(pairs) > 20 else None
            enso_years = [i for i, m in enumerate(meta) if abs(latest_at_or_before(self.oni, add_months(m[1], -1))) >= 1.0]
            enso_corr = float(np.corrcoef(y[enso_years], preds[enso_years])[0, 1]) if len(enso_years) > 20 else None
            self.models[lead] = Ridge(RIDGE_LAMBDA).fit(x, y)
            self.sigma[lead] = sigma
            skill[lead] = {
                "lead": lead,
                "samples": int(len(y)),
                "correlation": round(corr, 3),
                "msss": round(1 - mse_model / mse_clim, 3),
                "rpss": round(1 - rps_model / rps_clim, 3),
                "hitRate": round(hits / len(y), 3),
                "chirpsCorrelation": None if chirps_corr is None else round(chirps_corr, 3),
                "chirpsPairs": len(pairs),
                "strongEnsoCorrelation": None if enso_corr is None else round(enso_corr, 3),
                "sigma": round(sigma, 3),
            }
        first = min(min(c.totals) for c in self.climates.values())
        last = max(max(c.totals) for c in self.climates.values())
        self.skill = {
            "method": "Ridge regression ensemble (one model per lead month), tercile probabilities from cross-validated residual spread",
            "trainingData": f"NASA POWER monthly precipitation {first} to {last}, 11 regions, multiple sample points per region",
            "predictors": [label for _, label in FEATURES],
            "validation": "Leave-one-year-out cross-validation; independent check against CHIRPS v3.0 regional anomalies 2015-2024",
            "leads": [skill[l] for l in LEADS],
            "coefficients": {
                str(l): sorted(
                    ({"feature": label, "weight": round(float(c), 3)} for (_, label), c in zip(FEATURES, self.models[l].coef)),
                    key=lambda d: -abs(d["weight"]),
                )
                for l in LEADS
            },
        }

    def _merged_totals(self, region_id: str, recent: dict[str, float]):
        totals = dict(self.climates[region_id].totals)
        totals.update(recent)
        return totals

    def forecast(self, region: Region, recent_months: dict[str, float]):
        base = self.climates[region.id]
        clim = RegionClimate(self._merged_totals(region.id, recent_months), base.mean, base.std)
        issue = max(clim.totals)
        out = []
        for lead in LEADS:
            target = add_months(issue, lead)
            m = int(target[5:7])
            mean, std = base.mean[m], base.std[m]
            feats = build_features(region, clim, issue, target, self.oni, self.dmi)
            dry = mean < WET_MONTH_MM or feats is None
            if dry:
                mu, sigma = 0.0, 1.0
                probs = (1 / 3, 1 / 3, 1 / 3)
                contribs = []
            else:
                arr = np.array([feats])
                model = self.models[lead]
                mu = float(model.predict(arr)[0])
                sigma = self.sigma[lead]
                probs = tercile_probs(mu, sigma)
                parts = model.contributions(arr)[0]
                contribs = sorted(
                    ({"feature": label, "effect": round(float(v), 3)} for (_, label), v in zip(FEATURES, parts) if abs(v) >= 0.02),
                    key=lambda d: -abs(d["effect"]),
                )[:5]
            expected = max(0.0, mean + mu * std)
            low = max(0.0, mean + (mu - 1.2816 * sigma) * std)
            high = max(0.0, mean + (mu + 1.2816 * sigma) * std)
            lean = "dry" if probs[0] >= 0.45 else ("wet" if probs[2] >= 0.45 else "neutral")
            out.append(
                {
                    "month": target,
                    "monthName": MONTHS[m - 1],
                    "lead": lead,
                    "drySeason": dry,
                    "expectedMm": round(expected, 0),
                    "normalMm": round(mean, 0),
                    "rangeMm": [round(low, 0), round(high, 0)],
                    "pctOfNormal": round(expected / mean * 100, 0) if mean > 0 else None,
                    "zScore": round(mu, 2),
                    "probabilities": {"below": round(probs[0], 3), "near": round(probs[1], 3), "above": round(probs[2], 3)},
                    "lean": lean,
                    "drivers": contribs,
                }
            )
        return {"issuedFrom": issue, "months": out}


engine = ForecastEngine()
