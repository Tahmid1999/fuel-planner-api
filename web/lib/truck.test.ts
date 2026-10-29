import { checkInputs, DEFAULT_INPUTS, loadTruck, saveTruck } from "./truck";

afterEach(() => {
  localStorage.clear();
  jest.restoreAllMocks();
});

it("defaults pass the checks", () => {
  expect(checkInputs(DEFAULT_INPUTS)).toEqual({});
});

it("start at or below reserve fails on start_pct", () => {
  const errors = checkInputs({ ...DEFAULT_INPUTS, start_pct: 10, reserve_pct: 15 });
  expect(Object.keys(errors)).toEqual(["start_pct"]);
});

it("reserve too small for the detour", () => {
  const errors = checkInputs({ ...DEFAULT_INPUTS, mpg: 3, reserve_pct: 0, max_detour_mi: 10 });
  // 6.67 gal of a 150 gal tank is 4.44%; the message rounds up so the
  // number it gives actually passes
  expect(errors.reserve_pct).toBe("at least 4.5% for a 10 mi detour");
  expect(checkInputs({ ...DEFAULT_INPUTS, mpg: 3, reserve_pct: 4.5, max_detour_mi: 10 })).toEqual({});
});

it("reserve just under 50 is allowed, like the api", () => {
  expect(checkInputs({ ...DEFAULT_INPUTS, start_pct: 100, reserve_pct: 49.9995 })).toEqual({});
});

it("nan fails", () => {
  expect(checkInputs({ ...DEFAULT_INPUTS, mpg: NaN }).mpg).toBe("between 3 and 15");
});

it("ranges match the api", () => {
  expect(checkInputs({ ...DEFAULT_INPUTS, tank_gal: 401 }).tank_gal).toBeDefined();
  expect(checkInputs({ ...DEFAULT_INPUTS, reserve_pct: 50 }).reserve_pct).toBeDefined();
  expect(checkInputs({ ...DEFAULT_INPUTS, max_detour_mi: 10.5 }).max_detour_mi).toBeDefined();
  expect(checkInputs({ ...DEFAULT_INPUTS, start_pct: 100 })).toEqual({});
});

it("saved truck comes back without start_pct", () => {
  saveTruck({ ...DEFAULT_INPUTS, mpg: 7.2, start_pct: 90 });
  expect(loadTruck()).toEqual({ ...DEFAULT_INPUTS, mpg: 7.2 });
});

it("corrupt storage falls back to defaults", () => {
  localStorage.setItem("fuel-planner.truck", "{oops");
  expect(loadTruck()).toEqual(DEFAULT_INPUTS);
  localStorage.setItem("fuel-planner.truck", JSON.stringify({ mpg: "fast" }));
  expect(loadTruck()).toEqual(DEFAULT_INPUTS);
});

it("storage that throws falls back to defaults", () => {
  jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("SecurityError");
  });
  jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("SecurityError");
  });
  expect(loadTruck()).toEqual(DEFAULT_INPUTS);
  expect(() => saveTruck(DEFAULT_INPUTS)).not.toThrow();
});
