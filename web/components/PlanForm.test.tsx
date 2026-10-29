import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ApiError, createPlan, searchCities } from "@/lib/api";
import { DEFAULT_INPUTS, saveTruck } from "@/lib/truck";

import PlanForm from "./PlanForm";

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  createPlan: jest.fn(),
  searchCities: jest.fn(),
}));
jest.mock("@/lib/truck", () => ({
  ...jest.requireActual("@/lib/truck"),
  saveTruck: jest.fn(),
}));
const push = jest.fn();
jest.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const create = createPlan as jest.Mock;
const austin = { id: 1, label: "Austin, TX" };
const chicago = { id: 2, label: "Chicago, IL" };
const trip = { from: austin, to: chicago, inputs: DEFAULT_INPUTS };

function setup(initial?: typeof trip) {
  const user = userEvent.setup({ delay: null });
  render(<PlanForm initial={initial} />);
  return { user, submit: () => user.click(screen.getByRole("button", { name: /plan trip/i })) };
}

const field = (label: string) => screen.getByLabelText(label) as HTMLInputElement;

async function openLimits(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByText("Limits"));
}

async function retype(user: ReturnType<typeof userEvent.setup>, label: string, value: string) {
  await user.clear(field(label));
  await user.type(field(label), value);
}

beforeEach(() => {
  create.mockReset();
  push.mockReset();
  (saveTruck as jest.Mock).mockReset();
  (searchCities as jest.Mock).mockResolvedValue([]);
  localStorage.clear();
});

afterEach(() => jest.useRealTimers());

it("fills defaults", async () => {
  const { user } = setup();
  await openLimits(user);
  expect(field("Miles per gallon").value).toBe("6.5");
  expect(field("Tank (gal)").value).toBe("150");
  expect(field("Tank now (%)").value).toBe("50");
  expect(field("Keep in reserve (%)").value).toBe("15");
  expect(field("Max detour off the route (mi)").value).toBe("3");
});

it("blocks a city typed but not picked", async () => {
  const { user, submit } = setup({ ...trip });
  const to = screen.getAllByRole("combobox")[1];
  await user.clear(to);
  await user.type(to, "chicago");
  await submit();
  expect(await screen.findByText("pick a city from the list")).toBeInTheDocument();
  expect(create).not.toHaveBeenCalled();
});

it("blocks the same city twice", async () => {
  const { submit } = setup({ ...trip, to: austin });
  await submit();
  expect(await screen.findByText("pick a different city from the start")).toBeInTheDocument();
  expect(create).not.toHaveBeenCalled();
});

it("client check stops a start below the reserve", async () => {
  const { user, submit } = setup(trip);
  await retype(user, "Tank now (%)", "10");
  await submit();
  expect(await screen.findByText("above the reserve, at most 100")).toBeInTheDocument();
  expect(create).not.toHaveBeenCalled();
});

it("submits and goes to the plan page", async () => {
  create.mockResolvedValue({ id: "abc123" });
  const { submit } = setup(trip);
  await submit();
  expect(create).toHaveBeenCalledWith({ from_city: 1, to_city: 2, ...DEFAULT_INPUTS });
  expect(push).toHaveBeenCalledWith("/plans/abc123");
  expect(saveTruck).toHaveBeenCalledWith(DEFAULT_INPUTS);
});

it("server field errors land on the fields and open the limits", async () => {
  const msg = "Too small for a 10 mile detour: keep at least 6.7 gallons.";
  create.mockRejectedValue(new ApiError(400, "check the highlighted fields", { reserve_pct: [msg] }));
  const { submit } = setup(trip);
  await submit();
  expect(await screen.findByText(msg)).toBeVisible();
});

it("a 422 shows the detail above the button", async () => {
  const detail = "no fuel stop within range between mile 30.0 and mile 210.0 (180.0 mi)";
  create.mockRejectedValue(new ApiError(422, detail));
  const { submit } = setup(trip);
  await submit();
  expect(within(await screen.findByRole("alert")).getByText(detail)).toBeInTheDocument();
});

it("a slow server shows the waking notice and allows no second submit", async () => {
  jest.useFakeTimers();
  create.mockReturnValue(new Promise(() => {}));
  const user = userEvent.setup({ delay: null, advanceTimers: jest.advanceTimersByTime });
  render(<PlanForm initial={trip} />);
  const button = screen.getByRole("button", { name: /plan trip/i });
  await user.click(button);
  // antd submits after async validation, outside act; wait for the render
  await waitFor(() => expect(button).toHaveClass("ant-btn-loading"));
  await act(async () => {
    jest.advanceTimersByTime(5000);
  });
  expect(screen.getByText(/waking the server/)).toBeInTheDocument();
  await user.click(button);
  expect(create).toHaveBeenCalledTimes(1);
  jest.useRealTimers();
});

it("a timeout says so and lets the driver try again", async () => {
  create.mockRejectedValueOnce(new ApiError(0, "the server took too long to answer"));
  const { submit } = setup(trip);
  await submit();
  expect(await screen.findByText("the server took too long to answer")).toBeInTheDocument();
  create.mockResolvedValue({ id: "x" });
  await submit();
  expect(create).toHaveBeenCalledTimes(2);
});

it("an error goes away once the input that caused it is fixed elsewhere", async () => {
  create.mockReturnValue(new Promise(() => {}));
  const { user, submit } = setup(trip);
  await retype(user, "Tank now (%)", "10");
  await submit();
  expect(await screen.findByText("above the reserve, at most 100")).toBeInTheDocument();
  await openLimits(user);
  await retype(user, "Keep in reserve (%)", "5");
  await submit();
  await waitFor(() => expect(create).toHaveBeenCalled());
  // the message fades out (an animation jsdom never finishes); the field's
  // error state is what counts
  await waitFor(() =>
    expect(field("Tank now (%)").closest(".ant-form-item")).not.toHaveClass(
      "ant-form-item-has-error",
    ),
  );
}, 60_000);
