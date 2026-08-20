import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { CityCount } from "../api/types";
import { PublicHeader } from "../components/AppShell";
import { ErrorState, LoadingState } from "../components/Ui";

interface Statistics {
  count: number;
  averageAge: number | null;
  cities: CityCount[];
}

async function loadStatistics(): Promise<Statistics> {
  const [count, average, cities] = await Promise.all([
    apiRequest<{ count: number }>("/stats/count", { authenticated: false }),
    apiRequest<{ average_age: number | null }>("/stats/average-age", { authenticated: false }),
    apiRequest<CityCount[]>("/stats/top-cities", { authenticated: false }),
  ]);
  return { count: count.count, averageAge: average.average_age, cities };
}

export function PublicStatsPage() {
  const { t } = useTranslation();
  const statistics = useQuery({ queryKey: ["public-statistics"], queryFn: loadStatistics });
  const maxCityCount = Math.max(...(statistics.data?.cities.map((city) => city.count) ?? [1]));

  return (
    <div className="public-page">
      <PublicHeader />
      <main className="public-content">
        <section className="stats-hero">
          <div>
            <p className="eyebrow">{t("stats.eyebrow")}</p>
            <h1>{t("stats.title")}</h1>
          </div>
          <p>{t("stats.intro")}</p>
        </section>
        {statistics.isPending ? <LoadingState /> : null}
        {statistics.error ? <ErrorState error={statistics.error} /> : null}
        {statistics.data ? (
          <section aria-label={t("stats.summary")} className="stats-grid">
            <article className="metric-card metric-primary">
              <span>{t("stats.activeUsers")}</span>
              <strong>{statistics.data.count.toLocaleString()}</strong>
              <small>{t("stats.activeUsersNote")}</small>
            </article>
            <article className="metric-card">
              <span>{t("stats.averageAge")}</span>
              <strong>{statistics.data.averageAge?.toFixed(1) ?? "—"}</strong>
              <small>{t("stats.years")}</small>
            </article>
            <article className="city-card">
              <header>
                <span>{t("stats.topCities")}</span>
                <small>{t("stats.byUsers")}</small>
              </header>
              {statistics.data.cities.length ? (
                <ol>
                  {statistics.data.cities.map((city) => (
                    <li key={city.city}>
                      <div><span>{city.city}</span><strong>{city.count}</strong></div>
                      <span className="city-bar"><i style={{ width: `${(city.count / maxCityCount) * 100}%` }} /></span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="muted">{t("stats.noCities")}</p>
              )}
            </article>
          </section>
        ) : null}
        <footer className="public-footer">
          <span>Tawzeevo</span>
          <p>{t("stats.footer")}</p>
        </footer>
      </main>
    </div>
  );
}
