import { useNavigate, useSearch } from "@tanstack/react-router";

import { useSummary } from "../api/queries";
import { STATUS_VIEW, type Status } from "./status";

type Cell = {
  label: string;
  status: Status | undefined;
  value: "answered" | "unresolved" | "approved" | "needs_review" | "error";
  tone: Status;
  desc: string;
};

const CELLS: Cell[] = [
  { label: "Answered", status: undefined, value: "answered", tone: "draft", desc: "draft + approved" },
  { label: "Unresolved", status: "unresolved", value: "unresolved", tone: "unresolved", desc: "no valid proof" },
  { label: "Approved", status: "approved", value: "approved", tone: "approved", desc: "safe to reuse" },
  { label: "Needs review", status: "needs_review", value: "needs_review", tone: "needs_review", desc: "source changed" },
  { label: "Error", status: "error", value: "error", tone: "error", desc: "model failed" },
];

export function StatsRow() {
  const summary = useSummary();
  const navigate = useNavigate();
  const active = useSearch({ strict: false }).status;
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
          onClick={() => void navigate({ to: ".", search: (prev) => ({ ...prev, status: c.status }) })}
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
