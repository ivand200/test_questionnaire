import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export function ReviewPanel({ questionId }: { questionId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["question", questionId];

  const question = useQuery({
    queryKey,
    queryFn: async () => {
      const { data, error } = await api.GET("/api/questions/{question_id}", {
        params: { path: { question_id: questionId } },
      });
      if (error || !data) throw new Error("question call failed");
      return data;
    },
  });

  const generate = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/questions/{question_id}/draft", {
        params: { path: { question_id: questionId } },
      });
      if (error || !data) throw new Error("draft call failed");
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKey, data);
      void queryClient.invalidateQueries({ queryKey: ["questions"] });
    },
  });

  if (question.isError) return <section>Could not load the question.</section>;
  if (!question.data) return <section>Loading...</section>;
  const q = question.data;
  const buttonLabel = q.allowed_actions.includes("retry") ? "Retry" : "Generate draft";
  const canAsk = q.allowed_actions.length > 0;

  return (
    <section>
      <h2>
        {q.id} [{q.status}]{q.label && <> [{q.label}]</>}
      </h2>
      <p>{q.text}</p>
      {q.answer && (
        <>
          <h3>Answer</h3>
          <p>{q.answer}</p>
        </>
      )}
      {q.status === "unresolved" && (
        <p>Review route: {q.owner ?? "No owner mapped"}</p>
      )}
      {q.error && <p role="alert">{q.error}</p>}
      {generate.isError && <p role="alert">Could not ask for a draft.</p>}
      {q.warnings.length > 0 && (
        <ul>
          {q.warnings.map((w) => (
            <li key={`${w.kind}:${w.passage_id ?? ""}`}>{w.message}</li>
          ))}
        </ul>
      )}
      {q.citations.length > 0 && (
        <>
          <h3>Evidence</h3>
          <ul>
            {q.citations.map((c) => (
              <li key={c.passage_id}>
                <strong>{c.passage_id}</strong>
                <blockquote>{c.excerpt}</blockquote>
              </li>
            ))}
          </ul>
        </>
      )}
      {q.replaced.length > 0 && (
        <>
          <h3>Replaced</h3>
          <ul>
            {q.replaced.map((r) => (
              <li key={r.passage_id}>
                <strong>{r.passage_id}</strong> (replaced by {r.replaced_by})
                <blockquote>
                  <del>{r.excerpt}</del>
                </blockquote>
              </li>
            ))}
          </ul>
        </>
      )}
      {canAsk && (
        <button type="button" disabled={generate.isPending} onClick={() => generate.mutate()}>
          {buttonLabel}
        </button>
      )}
    </section>
  );
}
