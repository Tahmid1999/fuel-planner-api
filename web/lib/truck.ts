import type { PlanInputs } from "./api";

// Must match api/planner/defaults.py.
export const DEFAULT_INPUTS: PlanInputs = {
  mpg: 6.5,
  tank_gal: 150,
  start_pct: 50,
  reserve_pct: 15,
  max_detour_mi: 3,
};

const KEY = "fuel-planner.truck";

const within = (n: number, lo: number, hi: number) => Number.isFinite(n) && n >= lo && n <= hi;

// Same rules as PlanRequestSerializer; the API still has the last word.
export function checkInputs(i: PlanInputs) {
  const errors: Partial<Record<keyof PlanInputs, string>> = {};
  if (!within(i.mpg, 3, 15)) errors.mpg = "between 3 and 15";
  if (!within(i.tank_gal, 20, 400)) errors.tank_gal = "between 20 and 400 gallons";
  if (!within(i.max_detour_mi, 0, 10)) errors.max_detour_mi = "0 to 10 miles";
  if (!within(i.reserve_pct, 0, 49.999)) {
    errors.reserve_pct = "0 to 49";
  } else if (!errors.mpg && !errors.tank_gal && !errors.max_detour_mi) {
    const needed = (2 * i.max_detour_mi) / i.mpg;
    if ((i.tank_gal * i.reserve_pct) / 100 < needed) {
      errors.reserve_pct = `keep at least ${needed.toFixed(1)} gal for a ${i.max_detour_mi} mi detour`;
    }
  }
  if (!within(i.start_pct, 0, 100) || (!errors.reserve_pct && i.start_pct <= i.reserve_pct)) {
    errors.start_pct = "above the reserve, at most 100";
  }
  return errors;
}

// A driver's truck rarely changes, so its numbers are kept between visits.
// The tank level changes every trip and always starts at the default.
export function loadTruck(): PlanInputs {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (!saved || typeof saved !== "object") return DEFAULT_INPUTS;
    const merged = { ...DEFAULT_INPUTS };
    for (const k of ["mpg", "tank_gal", "reserve_pct", "max_detour_mi"] as const) {
      if (typeof saved[k] === "number") merged[k] = saved[k];
    }
    return Object.keys(checkInputs(merged)).length ? DEFAULT_INPUTS : merged;
  } catch {
    return DEFAULT_INPUTS;
  }
}

export function saveTruck(i: PlanInputs) {
  const { mpg, tank_gal, reserve_pct, max_detour_mi } = i;
  try {
    localStorage.setItem(KEY, JSON.stringify({ mpg, tank_gal, reserve_pct, max_detour_mi }));
  } catch {
    // private windows can refuse storage; the next trip just starts from defaults
  }
}
