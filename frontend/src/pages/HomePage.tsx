import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export function HomePage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/health");
      if (error || !data) throw new Error("health call failed");
      return data;
    },
  });

  return (
    <main>
      <h1>Hello</h1>
      {health.data && <p>Backend: {health.data.status}</p>}
    </main>
  );
}
