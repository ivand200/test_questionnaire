import { useSummary } from "../api/queries";
import { STATUS_VIEW, useStatusFilter, type Status } from "./status";

type Cell = {
  label: string;
  status: Status | undefined;
  value: "answered" | "unresolved" | "approved" | "needs_review" | "error";
  tone: Status;
  desc: string;
};

const STATUS_DESC = {
  unresolved: "no valid proof",
  approved: "safe to reuse",
  needs_review: "source changed",
  error: "model failed",
} as const;

const CELLS: Cell[] = [
  { label: "Answered", status: undefined, value: "answered", tone: "draft", desc: "draft + approved" },
  ...(Object.keys(STATUS_DESC) as (keyof typeof STATUS_DESC)[]).map((s) => ({
    label: STATUS_VIEW[s].label,
    status: s,
    value: s,
    tone: s,
    desc: STATUS_DESC[s],
  })),
];

export function StatsRow() {
  const summary = useSummary();
  const { active, select } = useStatusFilter();
  if (!summary.data) return null;
  const counts = summary.data;
  return (
    <div className="stats stats-vertical sm:stats-horizontal grid-cols-2 sm:grid-cols-5 w-full border border-base-300 bg-base-100">
      {CELLS.map((c) => (
        <button
          key={c.label}
          type="button"
          className={`stat text-left hover:bg-base-200 ${active === c.status ? "bg-base-200" : ""}`}
          aria-pressed={active === c.status}
          onClick={() => select(c.status)}
        >
          <div className="stat-title">{c.label}</div>
          <div className={`stat-value text-3xl ${STATUS_VIEW[c.tone].text}`}>
            {counts[c.value]}
          </div>
          <div className="stat-desc">{c.desc}</div>
        </button>
      ))}
    </div>
  );
}
