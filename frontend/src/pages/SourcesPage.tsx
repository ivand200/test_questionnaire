import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import { useDocuments, useInvalidateWorkspace } from "../api/queries";
import { useToast } from "../components/toast";

// The Sources tab: one row for each document. The Bump button is the Case 5 demo in the browser.
export function SourcesPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const invalidateWorkspace = useInvalidateWorkspace();
  const documents = useDocuments();

  const bump = useMutation({
    mutationFn: async (documentId: string) => {
      const { data, error } = await api.POST("/api/documents/{document_id}/bump-version", {
        params: { path: { document_id: documentId } },
      });
      if (error || !data) throw new Error(`Could not bump ${documentId}.`);
      return data;
    },
    onSuccess: (data) => {
      // Documents reload too, besides the queue, the open question views and the Stats row.
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      void invalidateWorkspace();
      toast(`${data.id} is now version ${data.version}`);
    },
    onError: (e: Error) => toast(e.message, "error"),
  });

  if (documents.isError) {
    return (
      <p role="alert" className="text-sm text-error">
        Could not load the documents.
      </p>
    );
  }
  if (!documents.data) return <p className="text-sm text-base-content/60">Loading sources...</p>;

  return (
    <section className="rounded-box border border-base-300 bg-base-100">
      <div className="p-4">
        <h2 className="font-semibold">Sources</h2>
        <p className="text-sm text-base-content/70">
          A document is replaced only through its supersedes field. A newer date alone does not
          replace it. Bumping a version here is the Case 5 demo: approved answers that cite it go
          back to Needs review.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Version</th>
              <th>Date</th>
              <th>Authority</th>
              <th>Supersedes</th>
              <th>Passages</th>
              <th>
                <span className="sr-only">Bump</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {documents.data.map((d) => (
              <tr key={d.id}>
                <td className="font-mono font-semibold">{d.id}</td>
                <td className="tabular-nums">v{d.version}</td>
                <td className="tabular-nums">{d.date}</td>
                <td>
                  {d.replaced_by ? (
                    <span className="badge badge-warning badge-outline badge-sm">
                      replaced by {d.replaced_by}
                    </span>
                  ) : (
                    <span className="badge badge-success badge-outline badge-sm">current</span>
                  )}
                </td>
                <td className="font-mono text-xs">{d.supersedes_id ?? "—"}</td>
                <td className="max-w-md text-sm">
                  {d.passages.map((p) => (
                    <div key={p.id}>
                      <span className="font-mono text-xs text-base-content/60">{p.id}</span>{" "}
                      {p.text}
                    </div>
                  ))}
                </td>
                <td>
                  <button
                    type="button"
                    className="btn btn-xs"
                    disabled={bump.isPending}
                    onClick={() => bump.mutate(d.id)}
                  >
                    Bump to v{d.version + 1}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
