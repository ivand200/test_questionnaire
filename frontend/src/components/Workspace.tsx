import type { ReactNode } from "react";

import { LoadIssues } from "./LoadIssues";
import { Queue } from "./Queue";

export function Workspace({ children }: { children?: ReactNode }) {
  return (
    <main style={{ display: "flex", gap: "2rem", alignItems: "flex-start" }}>
      <div style={{ flex: 1 }}>
        <LoadIssues />
        <Queue />
      </div>
      {children && <div style={{ flex: 1 }}>{children}</div>}
    </main>
  );
}
