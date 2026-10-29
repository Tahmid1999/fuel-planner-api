import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { PlanDocument } from "@/lib/api";
import fixture from "@/test/fixtures/austin-chicago.json";

import PlanView from "./PlanView";

const doc = fixture as unknown as PlanDocument;

it("summary line", () => {
  render(<PlanView doc={doc} />);
  expect(screen.getByText("Austin, TX → Chicago, IL · 1,161 mi · 20 h 31 min")).toBeInTheDocument();
});

it("cost and leftover line", () => {
  render(<PlanView doc={doc} />);
  expect(screen.getByText("Fuel $289.99")).toBeInTheDocument();
  expect(
    screen.getByText("$353.86 at the pump, minus $63.86 of fuel still in the tank at the end"),
  ).toBeInTheDocument();
});

it("savings line", () => {
  render(<PlanView doc={doc} />);
  expect(screen.getByText("$38.28 less than filling up at a quarter tank")).toBeInTheDocument();
});

it("zero savings wording", () => {
  render(<PlanView doc={{ ...doc, savings: 0 }} />);
  expect(screen.getByText("Same as filling up at a quarter tank")).toBeInTheDocument();
});

it("no stops wording", () => {
  render(<PlanView doc={{ ...doc, plan: { ...doc.plan, stops: [] } }} />);
  expect(screen.getByText("No stop needed: the tank covers the trip.")).toBeInTheDocument();
});

it("stop rows in order with formatted numbers", () => {
  render(<PlanView doc={doc} />);
  const table = screen.getAllByRole("table")[0];
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows.map((r) => within(r).getByText(/PWI|CADOO|Quiktrip/).textContent)).toEqual([
    "PWI #168",
    "CADOO MILLS",
    "Quiktrip #7900",
  ]);
  const first = within(rows[0]);
  expect(first.getByText("$2.799")).toBeInTheDocument();
  expect(first.getByText("79.1 gal")).toBeInTheDocument();
  expect(first.getByText("$221.33")).toBeInTheDocument();
  expect(first.getByText(/mile 26\.5/)).toBeInTheDocument();
});

it("habit section is collapsed and expands", async () => {
  render(<PlanView doc={doc} />);
  expect(screen.queryByText("PILOT TRAVEL CENTERS #367")).not.toBeInTheDocument();
  await userEvent.click(screen.getByText("Quarter-tank habit: 2 stops, $328.27"));
  expect(await screen.findByText("PILOT TRAVEL CENTERS #367")).toBeInTheDocument();
});

it("footer shows prices and truck", () => {
  render(<PlanView doc={doc} />);
  expect(
    screen.getByText(
      "Prices: OPIS sample, as of 28 Nov 2025 · Truck 6.5 mpg, 150 gal, 50% at start, 15% reserve, stations within 3 mi",
    ),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Edit trip" })).toHaveAttribute(
    "href",
    `/?plan=${doc.id}`,
  );
});
