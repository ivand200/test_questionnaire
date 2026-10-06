import { useState, type ReactNode } from "react";

import { ApproverContext, DEFAULT_APPROVER } from "./approver";
import { LoadIssues } from "./LoadIssues";
import { Queue } from "./Queue";

export function Workspace({ children }: { children?: ReactNode }) {
  const [approver, setApprover] = useState(DEFAULT_APPROVER);
  return (
    <ApproverContext.Provider value={approver}>
      <header>
        <label>
          Approver{" "}
          <input value={approver} onChange={(e) => setApprover(e.target.value)} />
        </label>
      </header>
      <main style={{ display: "flex", gap: "2rem", alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <LoadIssues />
          <Queue />
        </div>
        {children && <div style={{ flex: 1 }}>{children}</div>}
      </main>
    </ApproverContext.Provider>
  );
}
