import type { ReactNode } from "react";

import { LoadIssues } from "./LoadIssues";
import { Queue } from "./Queue";
import { StatsRow } from "./StatsRow";

// The Questionnaire tab: Stats row, then the queue with the review panel beside it.
export function Workspace({ children }: { children?: ReactNode }) {
  return (
    <>
      <StatsRow />
      <LoadIssues />
      <main className="grid items-start gap-4 lg:grid-cols-[minmax(20rem,24rem)_minmax(0,1fr)]">
        <Queue />
        {children && <div>{children}</div>}
      </main>
    </>
  );
}
