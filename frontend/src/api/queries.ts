import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { Status } from "../components/status";
import { api } from "./client";

// The data of a call, or an error that names the call. Every query hook ends with this.
export function unwrap<T>(result: { data?: T; error?: unknown }, name: string): T {
  if (result.error || !result.data) throw new Error(`${name} call failed`);
  return result.data;
}

export function useSummary() {
  return useQuery({
    queryKey: ["summary"],
    queryFn: async () => unwrap(await api.GET("/api/summary"), "summary"),
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => unwrap(await api.GET("/api/health"), "health"),
  });
}

export function useDocuments() {
  return useQuery({
    queryKey: ["documents"],
    queryFn: async () => unwrap(await api.GET("/api/documents"), "documents"),
  });
}

export function useQuestions(status: Status | undefined) {
  return useQuery({
    queryKey: ["questions", status ?? "all"],
    queryFn: async () =>
      unwrap(await api.GET("/api/questions", { params: { query: { status } } }), "questions"),
  });
}

export function useQuestion(questionId: string) {
  return useQuery({
    queryKey: ["question", questionId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/questions/{question_id}", { params: { path: { question_id: questionId } } }),
        "question",
      ),
  });
}

// After a change on the Backend: the queue, the Stats row and the open question views reload.
export function useInvalidateWorkspace() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["questions", "summary", "question"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
    );
}
