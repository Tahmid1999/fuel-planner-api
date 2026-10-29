import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import PlanPage from "@/app/plans/[id]/page";
import { ApiError, getPlan } from "@/lib/api";

jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), getPlan: jest.fn() }));
jest.mock("next/navigation", () => ({ useParams: () => ({ id: "nope" }) }));
const load = getPlan as jest.Mock;

beforeEach(() => load.mockReset());

it("unknown plan shows no plan with this link", async () => {
  load.mockRejectedValue(new ApiError(404, "Not found."));
  render(<PlanPage />);
  expect(await screen.findByText("No plan with this link.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Plan a trip" })).toHaveAttribute("href", "/");
});

it("server error shows the detail and retries", async () => {
  load.mockRejectedValueOnce(new ApiError(0, "can't reach the server"));
  load.mockReturnValueOnce(new Promise(() => {}));
  render(<PlanPage />);
  expect(await screen.findByText("can't reach the server")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(load).toHaveBeenCalledTimes(2);
  expect(load).toHaveBeenLastCalledWith("nope");
});
