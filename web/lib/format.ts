// US units only for now; a Bangladesh mode would swap this file.

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const usd3 = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});
const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const oneDp = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export const money = (n: number) => usd.format(n);
export const price = (n: number) => usd3.format(n);
export const miles = (n: number) => `${whole.format(n)} mi`;
export const milesExact = (n: number) => `${oneDp.format(n)} mi`;
export const gallons = (n: number) => `${oneDp.format(n)} gal`;

export function duration(min: number) {
  const m = Math.round(min);
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

export function asOf(isoDate: string) {
  // A bare date parses as UTC midnight, so format it in UTC too or it slips a
  // day back anywhere west of Greenwich.
  return new Date(isoDate).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
