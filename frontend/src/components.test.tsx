import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import type { Meta } from "./api";
import { CourtPicker, type Selection } from "./components/CourtPicker";
import { DecisionCurve } from "./components/DecisionCurve";
import { Drivers } from "./components/Drivers";
import { formatDuration, rankPhrase } from "./format";
import { initialSelection } from "./pages/PredictPage";

const meta: Meta = {
  districts: [
    { district: "Pune", courts: [
      { court_id: "25-1", court_name: "JMFC Pune", district: "Pune", judge_position: "jmfc", categories: ["summary_criminal", "bail_remand"] },
      { court_id: "25-2", court_name: "Civil Court Pune", district: "Pune", judge_position: "civil court", categories: ["civil_suit"] },
    ] },
    { district: "Thane", courts: [
      { court_id: "21-1", court_name: "Civil Court Thane", district: "Thane", judge_position: "civil court", categories: ["civil_suit", "execution"] },
    ] },
  ],
  case_categories: [
    { id: "bail_remand", label: "Bail / remand application", criminal: true },
    { id: "civil_suit", label: "Civil suit", criminal: false },
    { id: "execution", label: "Execution petition", criminal: false },
    { id: "summary_criminal", label: "Summary criminal", criminal: true },
  ],
  snapshot_date: "2019-01-01", horizon_days: 1825, trained_on: "test", note: "",
};

function Harness({ start }: { start: Selection }) {
  const [sel, setSel] = useState(start);
  return (
    <>
      <CourtPicker meta={meta} value={sel} onChange={setSel} />
      <output data-testid="sel">{`${sel.district}|${sel.courtId}|${sel.category}`}</output>
    </>
  );
}

describe("format", () => {
  it("formats durations", () => {
    expect(formatDuration(12)).toBe("12 days");
    expect(formatDuration(200)).toBe("7 months");
    expect(formatDuration(579)).toBe("1.6 years");
    expect(formatDuration(null)).toBe("over 5 years");
  });
  it("phrases rank as faster or slower", () => {
    expect(rankPhrase(0.8).head).toBe("Faster than 80%");
    expect(rankPhrase(0.3).head).toBe("Slower than 70%");
  });
});

describe("CourtPicker", () => {
  it("keeps the case type when the new court hears it, else picks the court's first", () => {
    render(<Harness start={{ district: "Pune", courtId: "25-2", category: "civil_suit" }} />);
    fireEvent.change(screen.getByLabelText("District"), { target: { value: "Thane" } });
    expect(screen.getByTestId("sel").textContent).toBe("Thane|21-1|civil_suit");
    fireEvent.change(screen.getByLabelText("District"), { target: { value: "Pune" } });
    expect(screen.getByTestId("sel").textContent).toBe("Pune|25-1|summary_criminal");
  });
  it("groups case types the court rarely hears", () => {
    render(<Harness start={{ district: "Pune", courtId: "25-2", category: "civil_suit" }} />);
    const rare = screen.getByRole("group", { name: "Rarely heard here" });
    expect(rare.querySelectorAll("option")).toHaveLength(3);
  });
});

describe("initialSelection", () => {
  it("uses a valid court from the URL", () => {
    expect(initialSelection(meta, "21-1", "execution")).toEqual({ district: "Thane", courtId: "21-1", category: "execution" });
  });
  it("falls back to a Pune civil court", () => {
    expect(initialSelection(meta, "nope", null)).toEqual({ district: "Pune", courtId: "25-2", category: "civil_suit" });
  });
});

describe("Drivers", () => {
  it("hides negligible factors and colours by direction", () => {
    const { container } = render(
      <Drivers items={[
        { feature: "case_category", label: "Case type", value: "Civil suit", multiplier: 0.6 },
        { feature: "queue_ratio", label: "Queue ratio", value: "0.80", multiplier: 1.2 },
        { feature: "court_system", label: "Court system", value: "no", multiplier: 1.0 },
      ]} />,
    );
    expect(screen.queryByText("Court system")).toBeNull();
    expect(container.querySelectorAll(".bar span.down")).toHaveLength(1);
    expect(container.querySelectorAll(".bar span.up")).toHaveLength(1);
  });
});

describe("DecisionCurve", () => {
  it("describes the curve and offers a table view", () => {
    const curve = Array.from({ length: 262 }, (_, i) => ({ day: i * 7, decided: Math.min(1, (i * 7) / 2000) }));
    render(<DecisionCurve curve={curve} medianDays={1001} typicalDays={800} />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/after 1 year/);
    expect(screen.getByText("Show as table")).toBeInTheDocument();
    expect(screen.getByText(/Median:/)).toBeInTheDocument();
  });
});
