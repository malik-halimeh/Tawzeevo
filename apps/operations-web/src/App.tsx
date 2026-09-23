import { Link, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { AppShell, PublicHeader } from "./components/AppShell";
import { AdminRoute, ClientRoute, ProtectedRoute } from "./components/RouteGuards";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from "./pages/AuthPages";
import { ClientHomePage } from "./pages/ClientHomePage";
import { BackupCallbackPage } from "./pages/BackupCallbackPage";
import { LandingPage } from "./pages/LandingPage";
import { ProfilePage } from "./pages/ProfilePage";
import { PublicStatsPage } from "./pages/PublicStatsPage";
import { TenantsPage } from "./pages/TenantsPage";
import { UsersPage } from "./pages/UsersPage";

function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="entry-page public-page">
      <PublicHeader />
      <main className="not-found" id="main" tabIndex={-1}>
        <p className="eyebrow">404</p>
        <h1>{t("notFound.title")}</h1>
        <p>{t("notFound.body")}</p>
        <Link className="button" to="/">{t("notFound.action")}</Link>
      </main>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<LandingPage />} path="/" />
      <Route element={<PublicStatsPage />} path="/stats" />
      <Route element={<LoginPage />} path="/login" />
      <Route element={<RegisterPage />} path="/register" />
      <Route element={<ForgotPasswordPage />} path="/forgot-password" />
      <Route element={<ResetPasswordPage />} path="/reset-password" />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route element={<ClientRoute />}>
            <Route element={<ClientHomePage />} path="/workspace" />
            <Route element={<BackupCallbackPage />} path="/backup/google/callback" />
          </Route>
          <Route element={<ProfilePage />} path="/profile" />
          <Route element={<AdminRoute />}>
            <Route element={<AdminDashboardPage />} path="/admin" />
            <Route element={<UsersPage />} path="/admin/users" />
            <Route element={<ApplicationsPage />} path="/admin/applications" />
            <Route element={<TenantsPage />} path="/admin/tenants" />
          </Route>
        </Route>
      </Route>
      <Route element={<NotFoundPage />} path="*" />
    </Routes>
  );
}
