import { useNavigate, useParams } from "@tanstack/react-router";
import { useEffect } from "react";

import { useQuestions } from "../api/queries";
import { STATUS_VIEW, STATUSES, useStatusFilter, type Status } from "./status";

// Filter grid order: All, then the six statuses.
const FILTERS: { label: string; status: Status | undefined }[] = [
  { label: "All", status: undefined },
  ...STATUSES.map((status) => ({ label: STATUS_VIEW[status].label, status })),
];

// j and k must not fire while the user types.
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function Queue() {
  const navigate = useNavigate();
  const { active: filter, select } = useStatusFilter();
  const selected = useParams({ strict: false }).questionId;
  const questions = useQuestions(filter);
  const shown = questions.data ?? [];

  const open = (questionId: string) =>
    void navigate({
      to: "/questions/$questionId",
      params: { questionId },
      search: (prev) => prev,
    });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key !== "j" && e.key !== "k") || e.ctrlKey || e.metaKey || e.altKey) return;
      if (isTyping(e.target) || shown.length === 0) return;
      const at = shown.findIndex((q) => q.id === selected);
      const next = e.key === "j" ? at + 1 : at === -1 ? shown.length - 1 : at - 1;
      const target = shown[Math.min(Math.max(next, 0), shown.length - 1)];
      if (target && target.id !== selected) open(target.id);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <section className="rounded-box border border-base-300 bg-base-100">
      <div className="flex flex-col gap-3 p-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">
            Queue <span className="font-normal text-base-content/60">{shown.length}</span>
          </h2>
          <span className="hidden items-center gap-1 text-xs text-base-content/60 sm:flex">
            <kbd className="kbd kbd-xs">j</kbd>
            <kbd className="kbd kbd-xs">k</kbd> move
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2" role="group" aria-label="Filter by status">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              type="button"
              className={`btn btn-sm w-full px-2 ${filter === f.status ? "btn-active" : ""}`}
              aria-pressed={filter === f.status}
              onClick={() => select(f.status)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      {questions.isError && (
        <p className="border-t border-base-300 p-4 text-sm text-error">Could not load the questions.</p>
      )}
      {questions.data && (
        <ul className="list border-t border-base-300">
          {shown.length === 0 && (
            <li className="p-4 text-sm text-base-content/60">No questions with this status.</li>
          )}
          {shown.map((q) => (
            <li
              key={q.id}
              className={`list-row cursor-pointer items-center ${q.id === selected ? "bg-base-200" : "hover:bg-base-200/60"}`}
              role="button"
              tabIndex={0}
              aria-pressed={q.id === selected}
              onClick={() => open(q.id)}
              onKeyDown={(e) => {
                if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  open(q.id);
                }
              }}
            >
              <span className="font-mono text-xs text-base-content/60">{q.id}</span>
              <div className="min-w-0">
                <div className="truncate font-medium">{q.text}</div>
                <div className="text-xs text-base-content/60">
                  {q.topic}
                  {q.warning_count > 0 && ` · ⚠ ${q.warning_count}`}
                </div>
              </div>
              <span className={`badge badge-md ${STATUS_VIEW[q.status].badge}`}>
                {STATUS_VIEW[q.status].label}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
