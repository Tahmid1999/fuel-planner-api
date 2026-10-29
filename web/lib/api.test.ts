/** @jest-environment node */
import { ApiError, createPlan, searchCities } from "./api";

const fetchMock = jest.fn();
global.fetch = fetchMock;

function answer(status: number, body: unknown) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return Promise.resolve(new Response(text, { status }));
}

const trip = {
  from_city: 1,
  to_city: 2,
  mpg: 6.5,
  tank_gal: 150,
  start_pct: 50,
  reserve_pct: 15,
  max_detour_mi: 3,
};

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("expected a rejection");
}

afterEach(() => {
  fetchMock.mockReset();
  jest.useRealTimers();
});

it("createPlan posts json and returns the document", async () => {
  fetchMock.mockReturnValue(answer(201, { id: "abc" }));
  const doc = await createPlan(trip);
  expect(doc.id).toBe("abc");
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("http://localhost:8000/api/plans/");
  expect(init.method).toBe("POST");
  expect(init.headers["Content-Type"]).toBe("application/json");
  expect(JSON.parse(init.body)).toEqual(trip);
});

it("400 keeps field errors", async () => {
  const msg = "The tank has to start above the reserve.";
  fetchMock.mockReturnValue(answer(400, { start_pct: [msg] }));
  const err = await failure(createPlan(trip));
  expect(err).toBeInstanceOf(ApiError);
  expect(err.status).toBe(400);
  expect(err.fields.start_pct[0]).toBe(msg);
  expect(err.detail).toBe("check the highlighted fields");
});

it("422 uses the detail", async () => {
  const detail = "no fuel stop within range between mile 30.0 and mile 210.0 (180.0 mi)";
  fetchMock.mockReturnValue(answer(422, { detail }));
  expect((await failure(createPlan(trip))).detail).toBe(detail);
});

it("html error page gives a readable error", async () => {
  fetchMock.mockReturnValue(answer(502, "<html>Bad Gateway</html>"));
  const err = await failure(createPlan(trip));
  expect(err.status).toBe(502);
  expect(err.detail).toBe("the server answered with an error (502)");
});

it("network failure", async () => {
  fetchMock.mockReturnValue(Promise.reject(new TypeError("Failed to fetch")));
  const err = await failure(createPlan(trip));
  expect(err.status).toBe(0);
  expect(err.detail).toBe("can't reach the server");
});

function hangUntilAborted(_url: string, init: RequestInit) {
  return new Promise((_resolve, reject) => {
    init.signal?.addEventListener("abort", () =>
      reject(new DOMException("aborted", "AbortError")),
    );
  });
}

it("timeout after 90 seconds", async () => {
  jest.useFakeTimers();
  fetchMock.mockImplementation(hangUntilAborted);
  const pending = failure(createPlan(trip));
  jest.advanceTimersByTime(90_000);
  const err = await pending;
  expect(err.status).toBe(0);
  expect(err.detail).toBe("the server took too long to answer");
});

it("caller abort is not reported as a timeout", async () => {
  fetchMock.mockImplementation(hangUntilAborted);
  const caller = new AbortController();
  const pending = failure(searchCities("chi", caller.signal));
  caller.abort();
  const err = await pending;
  expect(err).not.toBeInstanceOf(ApiError);
  expect((err as unknown as Error).name).toBe("AbortError");
});

it("searchCities encodes the query", async () => {
  fetchMock.mockReturnValue(answer(200, []));
  await searchCities("san an");
  expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/cities/?q=san%20an");
});
