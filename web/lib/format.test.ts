import { asOf, duration, gallons, miles, milesExact, money, price } from "./format";

it("money", () => {
  expect(money(1234.56)).toBe("$1,234.56");
  expect(money(-3.1)).toBe("-$3.10");
});

it("price keeps three decimals", () => {
  expect(price(2.799)).toBe("$2.799");
});

it("miles", () => {
  expect(miles(1160.8)).toBe("1,161 mi");
  expect(milesExact(26.5)).toBe("26.5 mi");
});

it("gallons", () => {
  expect(gallons(79.1)).toBe("79.1 gal");
});

it("duration", () => {
  expect(duration(1231)).toBe("20 h 31 min");
  expect(duration(45)).toBe("45 min");
  expect(duration(60)).toBe("1 h 0 min");
});

it("asOf does not shift the date west of UTC", () => {
  process.env.TZ = "America/Los_Angeles";
  expect(asOf("2025-11-28")).toBe("28 Nov 2025");
});
