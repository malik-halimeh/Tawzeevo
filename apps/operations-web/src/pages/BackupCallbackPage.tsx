import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { CONNECT_RESULT_KEY, PENDING_CONNECT_KEY, completeGoogleConnect } from "../backup/connect";
import { ErrorState, PageHeader } from "../components/Ui";

/** Google sends the owner back here; the code is exchanged once and never shown or stored. */
export function BackupCallbackPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [error, setError] = useState<unknown>();

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state");
    let tenantId: string | null = null;
    try { tenantId = sessionStorage.getItem(PENDING_CONNECT_KEY); } catch { tenantId = null; }
    if (!code || !state || !tenantId) {
      setError(new Error(t("backup.callbackMissing")));
      return;
    }
    void completeGoogleConnect(tenantId, code, state)
      .then((connection) => {
        try {
          sessionStorage.removeItem(PENDING_CONNECT_KEY);
          sessionStorage.setItem(CONNECT_RESULT_KEY, JSON.stringify({ tenant_id: tenantId, email: connection.account_email }));
        } catch { /* the workspace simply opens without the notice */ }
        void navigate("/workspace", { replace: true });
      })
      .catch(setError);
  }, [navigate, params, t]);

  return (
    <section className="page-section">
      <PageHeader eyebrow={t("backup.kicker")} title={t("backup.callbackTitle")} description={t("backup.callbackBody")} />
      {error ? <ErrorState error={error} /> : <p className="form-status" role="status">{t("backup.working")}</p>}
    </section>
  );
}
