import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { api } from "../api/client";

export function Queue() {
  const queryClient = useQueryClient();
  const questions = useQuery({
    queryKey: ["questions"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/questions");
      if (error || !data) throw new Error("questions call failed");
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
