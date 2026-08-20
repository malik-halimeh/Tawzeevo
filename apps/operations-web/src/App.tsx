import { Navigate, Route, Routes } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { AppShell, PublicHeader } from "./components/AppShell";
import { AdminRoute, ClientRoute, ProtectedRoute } from "./components/RouteGuards";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { ClientHomePage } from "./pages/ClientHomePage";
import { ProfilePage } from "./pages/ProfilePage";
import { PublicStatsPage } from "./pages/PublicStatsPage";
import { TenantsPage } from "./pages/TenantsPage";
import { UsersPage } from "./pages/UsersPage";

function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="public-page">
      <PublicHeader />
      <main className="not-found">
        <span>404</span>
        <h1>{t("notFound.title")}</h1>
        <p>{t("notFound.body")}</p>
        <a className="button" href="/">{t("notFound.action")}</a>
      </main>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Navigate replace to="/stats" />} path="/" />
      <Route element={<PublicStatsPage />} path="/stats" />
      <Route element={<LoginPage />} path="/login" />
      <Route element={<RegisterPage />} path="/register" />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route element={<ClientRoute />}>
            <Route element={<ClientHomePage />} path="/workspace" />
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
