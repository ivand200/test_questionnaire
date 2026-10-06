import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export function LoadIssues() {
  const loadIssues = useQuery({
    queryKey: ["load-issues"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/load-issues");
      if (error || !data) throw new Error("load issues call failed");
      return data;
    },
  });

  if (!loadIssues.data || loadIssues.data.length === 0) return null;
  return (
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
  );
}
