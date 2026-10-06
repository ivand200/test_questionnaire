import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export function HomePage() {
  const questions = useQuery({
    queryKey: ["questions"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/questions");
      if (error || !data) throw new Error("questions call failed");
      return data;
    },
  });
  const loadIssues = useQuery({
    queryKey: ["load-issues"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/load-issues");
      if (error || !data) throw new Error("load issues call failed");
      return data;
    },
  });

  return (
    <main>
      <h1>Queue</h1>
      {loadIssues.data && loadIssues.data.length > 0 && (
        <section>
          <h2>Load issues</h2>
          <ul>
            {loadIssues.data.map((issue) => (
              <li key={`${issue.kind}:${issue.id}`}>
                {issue.kind} {issue.id}: {issue.message}
              </li>
            ))}
          </ul>
        </section>
      )}
      {questions.isError && <p>Could not load the questions.</p>}
      {questions.data && (
        <ul>
          {questions.data.map((q) => (
            <li key={q.id}>
              {q.id} [{q.status}] {q.text}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
