import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ApiError, searchCities } from "@/lib/api";

import CityInput from "./CityInput";

jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), searchCities: jest.fn() }));
const search = searchCities as jest.Mock;

const chicago = { id: 1, name: "Chicago", state: "IL", label: "Chicago, IL" };
const chico = { id: 2, name: "Chico", state: "CA", label: "Chico, CA" };

function setup(value = null as { id: number; label: string } | null) {
  const onChange = jest.fn();
  const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
  render(<CityInput value={value} onChange={onChange} placeholder="To" />);
  return { onChange, user, box: screen.getByRole("combobox") };
}

async function settle() {
  await act(async () => {
    jest.advanceTimersByTime(300);
  });
}

beforeEach(() => {
  jest.useFakeTimers();
  search.mockReset();
  search.mockResolvedValue([chicago, chico]);
});

afterEach(() => jest.useRealTimers());

it("searches after a pause, not per key", async () => {
  const { user, box } = setup();
  await user.type(box, "chic");
  await settle();
  expect(search).toHaveBeenCalledTimes(1);
  expect(search.mock.calls[0][0]).toBe("chic");
});

it("one letter does not search", async () => {
  const { user, box } = setup();
  await user.type(box, "c");
  await settle();
  expect(search).not.toHaveBeenCalled();
});

it("picking an option reports the city", async () => {
  const { user, box, onChange } = setup();
  await user.type(box, "chi");
  await settle();
  await user.click(await screen.findByText("Chicago, IL"));
  expect(onChange).toHaveBeenLastCalledWith({ id: 1, label: "Chicago, IL" });
});

it("typing after a pick clears it", async () => {
  const { user, box, onChange } = setup({ id: 1, label: "Chicago, IL" });
  await user.type(box, "x");
  expect(onChange).toHaveBeenLastCalledWith(null);
});

it("slow older answer does not replace newer suggestions", async () => {
  let releaseOld: (v: unknown) => void = () => {};
  search
    .mockImplementationOnce(() => new Promise((resolve) => (releaseOld = resolve)))
    .mockResolvedValueOnce([chico]);
  const { user, box } = setup();
  await user.type(box, "chi");
  await settle();
  await user.type(box, "co");
  await settle();
  expect(await screen.findByText("Chico, CA")).toBeInTheDocument();
  await act(async () => releaseOld([chicago]));
  expect(screen.queryByText("Chicago, IL")).not.toBeInTheDocument();
  expect(screen.getByText("Chico, CA")).toBeInTheDocument();
});

it("empty answer shows the no-match line", async () => {
  search.mockResolvedValue([]);
  const { user, box } = setup();
  await user.type(box, "zzq");
  await settle();
  expect(await screen.findByText("no US city starts with that")).toBeInTheDocument();
});

it("a slow search says the server is waking", async () => {
  search.mockReturnValue(new Promise(() => {}));
  const { user, box } = setup();
  await user.type(box, "chi");
  await settle();
  await act(async () => {
    jest.advanceTimersByTime(5000);
  });
  expect(await screen.findByText(/waking the server/)).toBeInTheDocument();
});

it("a failed search says why", async () => {
  search.mockRejectedValue(new ApiError(0, "can't reach the server"));
  const { user, box } = setup();
  await user.type(box, "chi");
  await settle();
  expect(await screen.findByText("can't reach the server")).toBeInTheDocument();
});
