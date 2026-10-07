import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";

import { api } from "../api/client";
import type { Status } from "./status";

const FILTERS: { label: string; status: Status | undefined }[] = [
  { label: "All", status: undefined },
  { label: "Draft", status: "draft" },
  { label: "Unresolved", status: "unresolved" },
  { label: "Approved", status: "approved" },
  { label: "Needs review", status: "needs_review" },
  { label: "Error", status: "error" },
  { label: "Not asked", status: "new" },
];

export function Queue() {
  const navigate = useNavigate();
  const filter = useSearch({ strict: false }).status;
  const questions = useQuery({
    queryKey: ["questions", filter ?? "all"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/questions", {
        params: { query: { status: filter } },
      });
      if (error || !data) throw new Error("questions call failed");
      return data;
    },
  });

  return (
    <section>
      <h1>Queue</h1>
      <div role="group" aria-label="Filter by status">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            aria-pressed={filter === f.status}
            onClick={() => void navigate({ to: ".", search: (prev) => ({ ...prev, status: f.status }) })}
          >
            {f.label}
          </button>
        ))}
      </div>
      {questions.isError && <p>Could not load the questions.</p>}
      {questions.data && (
        <ul>
          {questions.data.map((q) => (
            <li key={q.id}>
              <Link
                to="/questions/$questionId"
                params={{ questionId: q.id }}
                search={(prev) => prev}
              >
                {q.id}
              </Link>{" "}
              [{q.status}] {q.text}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
