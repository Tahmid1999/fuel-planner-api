export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// The free API host sleeps and takes about a minute to wake, so be patient
// before calling it a failure.
const TIMEOUT_MS = 90_000;

export type City = { id: number; name: string; state: string; label: string };
// What a form field holds; a City or a saved plan's Place both fit.
export type CityChoice = { id: number; label: string };
export type Place = { id: number; label: string; lat: number; lng: number };

export type Stop = {
  opis_id: string;
  name: string;
  address: string;
  city: string;
  state: string;
  lat: number;
  lng: number;
  mile: number;
  detour_mi: number;
  detour_gal: number;
  price: number;
  gallons: number;
  cost: number;
};

export type PlanPart = {
  stops: Stop[];
  spend: number;
  leftover_value: number;
  cost: number;
  gallons: number;
};

export type PlanInputs = {
  mpg: number;
  tank_gal: number;
  start_pct: number;
  reserve_pct: number;
  max_detour_mi: number;
};

export type PlanDocument = {
  id: string;
  created_at: string;
  from: Place;
  to: Place;
  inputs: PlanInputs;
  prices: { source: string; as_of: string };
  route: {
    distance_mi: number;
    duration_min: number;
    geometry: { type: "LineString"; coordinates: [number, number][] };
  };
  plan: PlanPart;
  baseline: PlanPart;
  savings: number;
};

export type ActivePrices = { source: string; as_of: string; station_count: number };

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public fields: Record<string, string[]> = {},
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, TIMEOUT_MS);
  const caller = init.signal;
  const forward = () => controller.abort();
  caller?.addEventListener("abort", forward);

  let res: Response;
  let text: string;
  try {
    res = await fetch(API_URL + path, { ...init, signal: controller.signal });
    text = await res.text();
  } catch (e) {
    if (timedOut) throw new ApiError(0, "the server took too long to answer");
    // A superseded request (newer city search) goes back as the AbortError.
    if (caller?.aborted) throw e;
    throw new ApiError(0, "can't reach the server");
  } finally {
    clearTimeout(timer);
    caller?.removeEventListener("abort", forward);
  }

  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    // an HTML error page from a proxy or the host
  }

  if (res.ok) {
    if (body === null) throw new ApiError(res.status, "the server sent an empty answer");
    return body as T;
  }
  if (!body || typeof body !== "object") {
    throw new ApiError(res.status, `the server answered with an error (${res.status})`);
  }
  if (res.status === 400) {
    throw new ApiError(400, "check the highlighted fields", body as Record<string, string[]>);
  }
  const detail = (body as { detail?: string }).detail;
  throw new ApiError(res.status, detail ?? `the server answered with an error (${res.status})`);
}

export function searchCities(q: string, signal?: AbortSignal) {
  return request<City[]>(`/api/cities/?q=${encodeURIComponent(q)}`, { signal });
}

export function activePrices() {
  return request<ActivePrices>("/api/prices/active/");
}

export function createPlan(
  body: { from_city: number; to_city: number } & PlanInputs,
  signal?: AbortSignal,
) {
  return request<PlanDocument>("/api/plans/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
}

export function getPlan(id: string) {
  return request<PlanDocument>(`/api/plans/${encodeURIComponent(id)}/`);
}
