import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import { useApprover } from "./approver";

// The Backend's refusal text (409 gives { detail: string }); a fallback for anything else.
function refusal(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  return typeof detail === "string" ? detail : fallback;
}

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
      if (error || !data) throw new Error(refusal(error, "Could not ask for a draft."));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKey, data);
      void queryClient.invalidateQueries({ queryKey: ["questions"] });
    },
  });

  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");

  const saveEdit = useMutation({
    mutationFn: async (answer: string) => {
      const { data, error } = await api.PUT("/api/questions/{question_id}/draft", {
        params: { path: { question_id: questionId } },
        body: { answer },
      });
      if (error || !data) throw new Error(refusal(error, "Could not save the edit."));
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(queryKey, data);
      void queryClient.invalidateQueries({ queryKey: ["questions"] });
      setEditing(false);
    },
  });

  const approver = useApprover();
  const approve = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/questions/{question_id}/approve", {
        params: { path: { question_id: questionId } },
        body: { approver },
      });
      if (error || !data) throw new Error(refusal(error, "Could not approve the answer."));
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
  const canAsk = q.allowed_actions.includes("generate") || q.allowed_actions.includes("retry");
  const canApprove = q.allowed_actions.includes("approve");
  const canEdit = q.allowed_actions.includes("edit");

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
      {q.edited && <p>Edited by reviewer · not reused until approved</p>}
      {q.approved && (
        <p>
          Approved by {q.approved.approver} · {new Date(q.approved.approved_at).toLocaleString()}
        </p>
      )}
      {q.note && <p>Note: {q.note}</p>}
      {q.status === "unresolved" && (
        <p>Review route: {q.owner ?? "No owner mapped"}</p>
      )}
      {q.error && <p role="alert">{q.error}</p>}
      {generate.isError && <p role="alert">{generate.error.message}</p>}
      {approve.isError && <p role="alert">{approve.error.message}</p>}
      {saveEdit.isError && <p role="alert">{saveEdit.error.message}</p>}
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
                {q.approved && <> (version {q.approved.source_versions[c.passage_id.split(":")[0]]})</>}
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
      {canEdit && !editing && (
        <button
          type="button"
          onClick={() => {
            setEditText(q.answer ?? "");
            setEditing(true);
          }}
        >
          Edit
        </button>
      )}
      {canEdit && editing && (
        <div>
          <textarea
            aria-label="Edited answer"
            rows={4}
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
          />
          <button
            type="button"
            disabled={saveEdit.isPending || editText.trim() === ""}
            onClick={() => saveEdit.mutate(editText)}
          >
            Save edit
          </button>
        </div>
      )}
      {canApprove && (
        <button type="button" disabled={approve.isPending} onClick={() => approve.mutate()}>
          Approve
        </button>
      )}
      {canAsk && (
        <button type="button" disabled={generate.isPending} onClick={() => generate.mutate()}>
          {buttonLabel}
        </button>
      )}
    </section>
  );
}
