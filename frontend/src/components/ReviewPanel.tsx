import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type { components } from "../api/api.d.ts";
import { useDocuments } from "../api/queries";
import { useApprover } from "./approver";
import { STATUS_VIEW } from "./status";
import { useToast } from "./toast";

type QuestionView = components["schemas"]["QuestionView"];
type Warning = components["schemas"]["Warning"];
type CallInfo = components["schemas"]["CallInfo"];

// The Backend's refusal text (409 gives { detail: string }); a fallback for anything else.
function refusal(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  return typeof detail === "string" ? detail : fallback;
}

const time = (iso: string) => new Date(iso).toLocaleString();

// A short title for each warning kind; the sentence comes from the Backend.
const WARNING_TITLE: Record<Warning["kind"], string> = {
  citation_not_found: "Citation not found",
  no_citation: "No citation",
  superseded: "Older version conflicts",
  source_changed: "Source changed",
  support_check: "Support check doubts the answer",
  support_check_failed: "Support check did not run",
};

const CALL_CHIP: Record<CallInfo["label"], { text: string; cls: string }> = {
  real: { text: "Real model call", cls: "badge-outline" },
  cached: { text: "Cached replay", cls: "badge-ghost" },
  simulated: { text: "Simulated", cls: "badge-warning badge-outline" },
};

function WarningAlerts({ warnings }: { warnings: Warning[] }) {
  return (
    <>
      {warnings.map((w, i) => (
        <div
          key={`${w.kind}:${w.passage_id ?? ""}:${i}`}
          role="alert"
          className="alert alert-soft alert-warning items-start text-base-content"
        >
          <span aria-hidden="true">⚠</span>
          <div>
            <div className="font-semibold">{WARNING_TITLE[w.kind]}</div>
            <div className="text-sm">{w.message}</div>
          </div>
        </div>
      ))}
    </>
  );
}

function EvidenceCard(props: {
  id: string;
  version: number | null | undefined;
  date: string | null | undefined;
  text: string;
  badge: React.ReactNode;
  replacedBy?: string;
}) {
  const replaced = props.replacedBy !== undefined;
  return (
    <div className="rounded-box border border-base-300 bg-base-100 p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-mono font-semibold">{props.id}</span>
        {props.badge}
        {props.date && <span className="text-base-content/60">{props.date}</span>}
        {replaced ? (
          <span className="badge badge-warning badge-outline badge-sm">replaced</span>
        ) : (
          <span className="badge badge-success badge-outline badge-sm">current</span>
        )}
      </div>
      <blockquote className={`mt-2 text-sm ${replaced ? "text-base-content/60 line-through" : ""}`}>
        {replaced ? (
          props.text
        ) : (
          <mark className="rounded bg-info/20 px-1 text-base-content">{props.text}</mark>
        )}
      </blockquote>
      {replaced && (
        <div className="mt-1 text-xs text-base-content/70">
          Replaced by {props.replacedBy} through supersedes. Kept here for reviewers.
        </div>
      )}
    </div>
  );
}

function Evidence({ q }: { q: QuestionView }) {
  const documents = useDocuments();
  // A draft has no saved version yet: the version is the one the cited document has now.
  const currentVersion = (passageId: string) =>
    documents.data?.find((d) => d.passages.some((p) => p.id === passageId))?.version;

  if (q.citations.length === 0) {
    return (
      <div className="rounded-box border border-dashed border-base-300 p-4 text-sm text-base-content/70">
        No cited passage.
        {q.status === "unresolved" && q.owner && (
          <>
            {" "}
            Route it to <b>{q.owner}</b>.
          </>
        )}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      {q.citations.map((c) => {
        const version = c.version ?? currentVersion(c.passage_id);
        return (
          <EvidenceCard
            key={c.passage_id}
            id={c.passage_id}
            version={version}
            date={c.date}
            text={c.excerpt}
            badge={
              c.source_changed ? (
                <span className="badge badge-accent badge-sm">
                  approved on v{c.version}, now v{c.current_version}
                </span>
              ) : (
                version != null && <span className="badge badge-ghost badge-sm">v{version}</span>
              )
            }
          />
        );
      })}
      {q.replaced.map((r) => (
        <EvidenceCard
          key={r.passage_id}
          id={r.passage_id}
          version={r.version}
          date={r.date}
          text={r.excerpt}
          replacedBy={r.replaced_by}
          badge={<span className="badge badge-ghost badge-sm">v{r.version}</span>}
        />
      ))}
    </div>
  );
}

function DraftAnswer({ q }: { q: QuestionView }) {
  const box = "rounded-box bg-base-200 p-4 text-base";
  if (q.error) {
    return (
      <div role="alert" className="alert alert-soft alert-error text-base-content">
        <div>
          <div className="font-semibold">{q.error}</div>
          <div className="text-sm">No draft was made. Other questions are not affected.</div>
        </div>
      </div>
    );
  }
  if (q.status === "new") {
    return (
      <div className={`${box} text-base-content/60`}>
        Not asked yet. Generate a draft to see the answer and its sources.
      </div>
    );
  }
  if (q.status === "unresolved") {
    return (
      <div className={`${box} text-base-content/70`}>
        <div className="font-medium text-base-content">No answer</div>
        {q.answer && <div className="mt-1 text-sm">Model note: {q.answer}</div>}
        <div className="mt-2 text-sm">
          Suggested owner: <b>{q.owner ?? "No owner mapped"}</b>
        </div>
      </div>
    );
  }
  return (
    <>
      <div className={box}>{q.answer}</div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-base-content/70">
        {q.edited && (
          <span className="badge badge-outline badge-sm">
            Edited by reviewer · not reused until approved
          </span>
        )}
        {q.approved && (
          <span>
            {q.status === "needs_review" ? "Previously approved by" : "Approved by"}{" "}
            <b>{q.approved.approver}</b> · {time(q.approved.approved_at)}
          </span>
        )}
      </div>
    </>
  );
}

function Provenance({ call }: { call: CallInfo | null | undefined }) {
  if (!call) return null;
  const chip = CALL_CHIP[call.label];
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-base-content/60">
      <span className="tooltip" data-tip={`${call.model} · ${time(call.when)}`}>
        <span className={`badge badge-sm ${chip.cls}`}>{chip.text}</span>
      </span>
      <span>
        {call.model} · {time(call.when)}
      </span>
    </div>
  );
}

export function ReviewPanel({ questionId }: { questionId: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
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

  // The new view replaces the cached one; the queue and the Stats row reload.
  const saved = (data: QuestionView) => {
    queryClient.setQueryData(queryKey, data);
    void queryClient.invalidateQueries({ queryKey: ["questions"] });
    void queryClient.invalidateQueries({ queryKey: ["summary"] });
  };
  const failed = (e: Error) => toast(e.message, "error");

  const generate = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/questions/{question_id}/draft", {
        params: { path: { question_id: questionId } },
      });
      if (error || !data) throw new Error(refusal(error, "Could not ask for a draft."));
      return data;
    },
    onSuccess: saved,
    onError: failed,
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
      saved(data);
      setEditing(false);
      toast("Edit saved.");
    },
    onError: failed,
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
      saved(data);
      toast("Approved.");
    },
    onError: failed,
  });

  const [noting, setNoting] = useState(false);
  const [noteText, setNoteText] = useState("");

  const leaveOpen = useMutation({
    mutationFn: async (note: string) => {
      const { data, error } = await api.POST("/api/questions/{question_id}/leave-open", {
        params: { path: { question_id: questionId } },
        body: { note },
      });
      if (error || !data) throw new Error(refusal(error, "Could not leave the question open."));
      return data;
    },
    onSuccess: (data) => {
      saved(data);
      setNoting(false);
      setNoteText("");
      toast(
        data.status === "needs_review"
          ? "Note saved. Status stays Needs review."
          : "Left open with a note.",
        "warning",
      );
    },
    onError: failed,
  });

  if (question.isError) return <section>Could not load the question.</section>;
  if (!question.data) return <section>Loading...</section>;
  const q = question.data;
  const can = (action: QuestionView["allowed_actions"][number]) => q.allowed_actions.includes(action);
  const askLabel = can("retry") ? "Retry" : "Generate draft";
  const canAsk = can("generate") || can("retry");
  // One primary button: Approve, or Generate and Retry when they are the only action.
  const askIsPrimary = canAsk && q.allowed_actions.length === 1;
  const view = STATUS_VIEW[q.status];

  return (
    <section className="card border border-base-300 bg-base-100">
      <div className="card-body gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-mono font-semibold">{q.id}</span>
            <span className="text-base-content/60">{q.topic}</span>
            <span className="text-base-content/60">· {q.owner ?? "No owner mapped"}</span>
            <span className={`badge ${view.badge} whitespace-nowrap`}>{view.label}</span>
          </div>
          <h2 className="mt-2 text-lg font-semibold">{q.text}</h2>
        </div>

        <WarningAlerts warnings={q.warnings} />

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-base-content/60">
              Draft answer
            </h3>
            <DraftAnswer q={q} />
          </div>
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-base-content/60">
              Evidence · {q.citations.length} cited
            </h3>
            <Evidence q={q} />
          </div>
        </div>

        {editing && can("edit") && (
          <fieldset className="fieldset">
            <legend className="fieldset-legend">Edit answer</legend>
            <textarea
              aria-label="Edited answer"
              className="textarea w-full"
              rows={3}
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                type="button"
                className="btn btn-sm"
                disabled={saveEdit.isPending || editText.trim() === ""}
                onClick={() => saveEdit.mutate(editText)}
              >
                Save edit
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>
                Cancel
              </button>
            </div>
          </fieldset>
        )}
        {noting && can("leave_open") ? (
          <fieldset className="fieldset">
            <legend className="fieldset-legend">Note for {q.owner ?? "the owner"}</legend>
            <textarea
              aria-label="Note"
              className="textarea w-full"
              rows={2}
              placeholder="What is missing or unclear?"
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                type="button"
                className="btn btn-sm"
                disabled={leaveOpen.isPending || noteText.trim() === ""}
                onClick={() => leaveOpen.mutate(noteText)}
              >
                Save note
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setNoting(false)}>
                Cancel
              </button>
            </div>
          </fieldset>
        ) : (
          q.note && (
            <div className="rounded-box bg-base-200 p-3 text-sm">
              <span className="font-semibold">Note:</span> {q.note}
            </div>
          )
        )}

        <div className="flex flex-wrap items-center gap-2 border-t border-base-300 pt-4">
          {generate.isPending && (
            <button type="button" className="btn" disabled>
              <span className="loading loading-spinner loading-sm" />
              Asking the model…
            </button>
          )}
          {!generate.isPending && canAsk && (
            <button
              type="button"
              className={`btn ${askIsPrimary ? "btn-primary" : ""}`}
              onClick={() => generate.mutate()}
            >
              {askLabel}
            </button>
          )}
          {can("edit") && (
            <button
              type="button"
              className="btn"
              onClick={() => {
                setEditText(q.answer ?? "");
                setEditing(true);
              }}
            >
              Edit
            </button>
          )}
          {can("leave_open") && (
            <button
              type="button"
              className="btn"
              onClick={() => {
                setNoteText(q.note ?? "");
                setNoting(true);
              }}
            >
              Leave open + note
            </button>
          )}
          {can("approve") && (
            <button
              type="button"
              className="btn btn-primary"
              disabled={approve.isPending}
              onClick={() => approve.mutate()}
            >
              Approve
            </button>
          )}
          {can("ask_again") && !generate.isPending && (
            <button type="button" className="btn btn-ghost" onClick={() => generate.mutate()}>
              Ask this question again
            </button>
          )}
        </div>

        <Provenance call={q.call} />
      </div>
    </section>
  );
}
