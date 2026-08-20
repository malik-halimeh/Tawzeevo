import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "../auth/AuthContext";

export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();
  const { t } = useTranslation();
  if (status === "loading") {
    return <div className="full-page-status" role="status">{t("common.loadingSession")}</div>;
  }
  if (status === "unauthenticated") {
    return <Navigate replace state={{ from: location.pathname }} to="/login" />;
  }
  return <Outlet />;
}

export function AdminRoute() {
  const { user } = useAuth();
  if (user?.type !== "admin") return <Navigate replace to="/workspace" />;
  return <Outlet />;
}

export function ClientRoute() {
  const { user } = useAuth();
  if (user?.type !== "client") return <Navigate replace to="/admin" />;
  return <Outlet />;
}
