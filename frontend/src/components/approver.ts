import { createContext, useContext } from "react";

export const DEFAULT_APPROVER = "Sales reviewer";

// The approver name typed in the header; Approve sends it.
export const ApproverContext = createContext<string>(DEFAULT_APPROVER);

export function useApprover(): string {
  return useContext(ApproverContext);
}
