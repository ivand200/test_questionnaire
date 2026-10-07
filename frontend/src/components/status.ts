export type Status = "new" | "draft" | "unresolved" | "approved" | "needs_review" | "error";

export const STATUSES: Status[] = ["draft", "unresolved", "needs_review", "approved", "error", "new"];

// The only logic on the screen: a status to its label and colour. Full class names, so Tailwind finds them.
export const STATUS_VIEW: Record<Status, { label: string; text: string }> = {
  new: { label: "Not asked", text: "text-base-content" },
  draft: { label: "Draft", text: "text-info" },
  unresolved: { label: "Unresolved", text: "text-warning" },
  approved: { label: "Approved", text: "text-success" },
  needs_review: { label: "Needs review", text: "text-accent" },
  error: { label: "Error", text: "text-error" },
};
