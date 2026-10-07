import type { ReactNode } from "react";

import { LoadIssues } from "./LoadIssues";
import { Queue } from "./Queue";
import { StatsRow } from "./StatsRow";

// The Questionnaire tab: Stats row, then the queue with the review panel beside it.
export function Workspace({ children }: { children?: ReactNode }) {
  return (
    <>
      <StatsRow />
      <main style={{ display: "flex", gap: "2rem", alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <LoadIssues />
          <Queue />
        </div>
        {children && <div style={{ flex: 1 }}>{children}</div>}
      </main>
    </>
  );
}
