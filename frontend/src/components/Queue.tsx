import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { api } from "../api/client";

export function Queue() {
  const questions = useQuery({
    queryKey: ["questions"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/questions");
      if (error || !data) throw new Error("questions call failed");
      return data;
    },
  });

  return (
    <section>
      <h1>Queue</h1>
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
