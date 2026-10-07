export type Status = "new" | "draft" | "unresolved" | "approved" | "needs_review" | "error";

export const STATUSES: Status[] = ["draft", "unresolved", "needs_review", "approved", "error", "new"];

// The only logic on the screen: a status to its label and colour. Full class names, so Tailwind finds them.
export const STATUS_VIEW: Record<Status, { label: string; text: string; badge: string }> = {
  new: { label: "Not asked", text: "text-base-content", badge: "badge-ghost" },
  draft: { label: "Draft", text: "text-info", badge: "badge-info" },
  unresolved: { label: "Unresolved", text: "text-warning", badge: "badge-warning" },
  approved: { label: "Approved", text: "text-success", badge: "badge-success" },
  needs_review: { label: "Needs review", text: "text-accent", badge: "badge-accent" },
  error: { label: "Error", text: "text-error", badge: "badge-error" },
};
