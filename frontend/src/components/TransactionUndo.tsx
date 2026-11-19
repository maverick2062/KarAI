import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";
import { TransactionsApi } from "../api/endpoints";
import { playNotificationSound } from "../utils/sound";

type UndoAction = {
  transactionIds: string[];
  action: "delete" | "complete";
  expiresAt: number;
};

interface TransactionUndoContextValue {
  undoAction: UndoAction | null;
  isUndoing: boolean;
  startUndo: (transactionIds: string | string[], action: UndoAction["action"]) => void;
}

const TransactionUndoContext = createContext<TransactionUndoContextValue | undefined>(undefined);

function undoErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return typeof error.detail === "string" ? error.detail : "Could not undo this transaction action.";
  }
  return "Could not undo this transaction action.";
}

export function TransactionUndoProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [undoAction, setUndoAction] = useState<UndoAction | null>(null);
  const [isUndoing, setIsUndoing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clock, setClock] = useState(Date.now());

  useEffect(() => {
    if (!undoAction) return;
    const remaining = undoAction.expiresAt - Date.now();
    if (remaining <= 0) {
      setUndoAction(null);
      return;
    }

    const currentExpiresAt = undoAction.expiresAt;
    const timeout = window.setTimeout(() => setUndoAction(null), remaining);
    const clockInterval = window.setInterval(() => setClock(Date.now()), 1000);
    function handleVisibilityChange() {
      if (document.visibilityState === "visible" && Date.now() >= currentExpiresAt) {
        setUndoAction(null);
      }
    }
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      window.clearTimeout(timeout);
      window.clearInterval(clockInterval);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [undoAction]);

  useEffect(() => {
    if (!user) {
      setUndoAction(null);
      setError(null);
    }
  }, [user]);

  function startUndo(transactionIds: string | string[], action: UndoAction["action"]) {
    const ids = Array.isArray(transactionIds) ? transactionIds : [transactionIds];
    if (ids.length === 0) return;
    setError(null);
    setClock(Date.now());
    setUndoAction({ transactionIds: ids, action, expiresAt: Date.now() + 45_000 });
    playNotificationSound();
  }

  async function undoLastAction() {
    if (!undoAction || isUndoing) return;
    if (Date.now() >= undoAction.expiresAt) {
      setUndoAction(null);
      return;
    }

    setIsUndoing(true);
    setError(null);
    try {
      if (undoAction.action === "delete") {
        if (undoAction.transactionIds.length === 1) {
          await TransactionsApi.restore(undoAction.transactionIds[0]);
        } else {
          await TransactionsApi.batchRestore(undoAction.transactionIds);
        }
      } else {
        if (undoAction.transactionIds.length === 1) {
          await TransactionsApi.reopen(undoAction.transactionIds[0]);
        } else {
          await TransactionsApi.batchReopen(undoAction.transactionIds);
        }
      }
      setUndoAction(null);
      playNotificationSound();
      window.dispatchEvent(new Event("karai-transactions-updated"));
    } catch (err) {
      setError(undoErrorMessage(err));
    } finally {
      setIsUndoing(false);
    }
  }

  const remainingSeconds = undoAction
    ? Math.max(0, Math.ceil((undoAction.expiresAt - clock) / 1000))
    : 0;

  const undoMessage = undoAction
    ? undoAction.transactionIds.length === 1
      ? undoAction.action === "delete"
        ? `Transaction removed. Undo available for ${remainingSeconds}s.`
        : `Transaction marked as completed. Undo available for ${remainingSeconds}s.`
      : undoAction.action === "delete"
        ? `${undoAction.transactionIds.length} transactions removed. Undo available for ${remainingSeconds}s.`
        : `${undoAction.transactionIds.length} transactions marked as completed. Undo available for ${remainingSeconds}s.`
    : "";

  return (
    <TransactionUndoContext.Provider value={{ undoAction, isUndoing, startUndo }}>
      {children}
      {undoAction && (
        <div className="toast toast--undo" role={error ? "alert" : "status"} aria-live={error ? "assertive" : "polite"}>
          <div className="toast__body">
            <span>{error ? error : undoMessage}</span>
            <button type="button" className="button button--secondary" onClick={undoLastAction} disabled={isUndoing}>
              {isUndoing ? "Undoing…" : "Undo"}
            </button>
          </div>
          <div
            className="toast__progress toast__progress--undo"
            style={{ transform: `scaleX(${remainingSeconds / 45})` }}
            aria-hidden="true"
          />
        </div>
      )}
    </TransactionUndoContext.Provider>
  );
}

export function useTransactionUndo(): TransactionUndoContextValue {
  const context = useContext(TransactionUndoContext);
  if (!context) throw new Error("useTransactionUndo must be used within a TransactionUndoProvider");
  return context;
}
