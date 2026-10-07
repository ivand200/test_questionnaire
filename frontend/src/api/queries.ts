import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

export function useSummary() {
  return useQuery({
    queryKey: ["summary"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/summary");
      if (error || !data) throw new Error("summary call failed");
      return data;
    },
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/health");
      if (error || !data) throw new Error("health call failed");
      return data;
    },
  });
}
