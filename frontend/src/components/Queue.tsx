import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { api } from "../api/client";

type Status = "new" | "draft" | "unresolved" | "approved" | "needs_review" | "error";

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
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Status | undefined>(undefined);
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
  const summary = useQuery({
    queryKey: ["summary"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/summary");
      if (error || !data) throw new Error("summary call failed");
      return data;
    },
  });

  const runAll = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/questionnaire/run");
      if (error || !data) throw new Error("run all call failed");
      return data;
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["questions"] });
      void queryClient.invalidateQueries({ queryKey: ["summary"] });
      void queryClient.invalidateQueries({ queryKey: ["question"] });
    },
  });

  return (
    <section>
      <h1>Queue</h1>
      <button type="button" disabled={runAll.isPending} onClick={() => runAll.mutate()}>
        Run all
      </button>
      {runAll.isError && <p role="alert">Could not run all questions.</p>}
      {summary.data && (
        <p>
          Not asked {summary.data.new} · Draft {summary.data.draft} · Unresolved{" "}
          {summary.data.unresolved} · Approved {summary.data.approved} · Needs review{" "}
          {summary.data.needs_review} · Error{" "}
          {summary.data.error} · Answered {summary.data.answered}
        </p>
      )}
      <div role="group" aria-label="Filter by status">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            aria-pressed={filter === f.status}
            onClick={() => setFilter(f.status)}
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
              <Link to="/questions/$questionId" params={{ questionId: q.id }}>
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
