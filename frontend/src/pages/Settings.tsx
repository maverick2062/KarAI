import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { UsersApi } from "../api/endpoints";
import { ApiError } from "../api/client";
import { DisclaimerBanner } from "../components/DisclaimerBanner";

export function Settings() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [confirmText, setConfirmText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  async function handleDelete() {
    if (confirmText !== "DELETE") return;
    setError(null);
    setIsDeleting(true);
    try {
      await UsersApi.deleteMyAccount();
      await logout();
      navigate("/register");
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Could not delete account.");
      setIsDeleting(false);
    }
  }

  return (
    <div className="page">
      <DisclaimerBanner />
      <h1>Settings</h1>

      <div className="card">
        <h2>Account</h2>
        <p>
          <strong>Name:</strong> {user?.full_name}
        </p>
        <p>
          <strong>Email:</strong> {user?.email}
        </p>
      </div>

      <div className="card">
        <h2>API access</h2>
        <p className="empty-state">
          Programmatic ingestion via API keys (for tools like Tally/Zoho Books) is planned but not built in
          this prototype.
        </p>
      </div>

      <div className="card card--danger">
        <h2>Delete my data</h2>
        <p>
          Permanently deletes your account and every transaction, TDS event, AIS record, and report tied to
          it. This cannot be undone — it's how you revoke consent and exercise your right to erasure under
          the DPDP Act 2023.
        </p>
        {error && <div className="alert alert--error">{error}</div>}
        <label>
          Type <strong>DELETE</strong> to confirm
          <input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />
        </label>
        <button
          className="button button--danger"
          disabled={confirmText !== "DELETE" || isDeleting}
          onClick={handleDelete}
        >
          {isDeleting ? "Deleting…" : "Permanently delete my account"}
        </button>
      </div>
    </div>
  );
}
