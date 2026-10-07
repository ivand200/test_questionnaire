import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Kind = "success" | "info" | "warning" | "error";
type Toast = { id: number; message: string; kind: Kind };

const TOAST_MS = 3000;

// Full class names, so Tailwind finds them.
const ALERT: Record<Kind, string> = {
  success: "alert-success",
  info: "alert-info",
  warning: "alert-warning",
  error: "alert-error",
};

type Push = (message: string, kind?: Kind) => void;

const ToastContext = createContext<Push>(() => {});

// A short message for about 3 seconds after an action. Several can stack.
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback<Push>((message, kind = "success") => {
    const id = Date.now() + Math.random();
    setToasts((all) => [...all, { id, message, kind }]);
    setTimeout(() => setToasts((all) => all.filter((t) => t.id !== id)), TOAST_MS);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast toast-end z-50" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`alert ${ALERT[t.kind]} text-sm`}>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): Push {
  return useContext(ToastContext);
}
