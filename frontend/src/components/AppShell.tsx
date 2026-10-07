import { useMutation } from "@tanstack/react-query";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { useState } from "react";

import { api } from "../api/client";
import { useHealth, useInvalidateWorkspace, useSummary } from "../api/queries";
import { ApproverContext, DEFAULT_APPROVER } from "./approver";
import { ToastProvider } from "./toast";

export function AppShell() {
  const invalidateWorkspace = useInvalidateWorkspace();
  const [approver, setApprover] = useState(DEFAULT_APPROVER);
  const onSources = useRouterState({ select: (s) => s.location.pathname.startsWith("/sources") });
  const health = useHealth();
  const summary = useSummary();
  const todo = summary.data ? summary.data.new + summary.data.error : 0;

  const runAll = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/questionnaire/run");
      if (error || !data) throw new Error("run all call failed");
      return data;
    },
    onSettled: () => void invalidateWorkspace(),
  });

  return (
    <ApproverContext.Provider value={approver}>
      <ToastProvider>
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-6">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="text-2xl font-semibold">Questionnaire workspace</h1>
          <label className="flex items-center gap-2 text-sm" htmlFor="reviewer">
            Reviewer
            <input
              id="reviewer"
              className="input input-sm w-40"
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
            />
          </label>
        </header>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div role="tablist" className="tabs tabs-border">
            <Link to="/" role="tab" className={`tab ${onSources ? "" : "tab-active"}`}>
              Questionnaire
            </Link>
            <Link to="/sources" role="tab" className={`tab ${onSources ? "tab-active" : ""}`}>
              Sources
            </Link>
          </div>
          <div className="flex items-center gap-3">
            {health.data && (
              <span className="text-xs text-base-content/60">
                {health.data.mode === "real" ? "Real model calls" : "Replay mode · no API key"}
              </span>
            )}
            <button
              type="button"
              className="btn btn-neutral btn-sm"
              disabled={todo === 0 || runAll.isPending}
              onClick={() => runAll.mutate()}
            >
              Run all{todo > 0 ? ` (${todo})` : ""}
            </button>
          </div>
        </div>
        {runAll.isError && (
          <p role="alert" className="text-sm text-error">
            Could not run all questions.
          </p>
        )}
        <Outlet />
      </div>
      </ToastProvider>
    </ApproverContext.Provider>
  );
}
