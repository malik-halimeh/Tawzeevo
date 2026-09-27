import type { TFunction } from "i18next";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import { currentPosition } from "./devicePosition";

/** Directions preview state and wording (D-093); the view is DirectionsView. */
export interface Step { type: number; name: string | null; distance_m: number; duration_s: number; exit_number: number | null }
export interface Answer { method: string; distance_m: number; duration_s: number | null; points: [number, number][]; steps: Step[] }
export interface DirectionsResult extends Answer { taskId: string; customer: string }
export interface DirectionsTarget { id: string; customer_name: string }

export function useStopDirections(tenantId: string) {
  const { t } = useTranslation();
  const [result, setResult] = useState<DirectionsResult>();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<unknown>();
  const show = useCallback((task: DirectionsTarget) => {
    setBusy(true); setProblem(undefined); setResult(undefined);
    currentPosition()
      .then(async (here) => {
        if (!here) throw new Error(t("directions.noPosition"));
        const answer = await apiRequest<Answer>(`/api/v1/routes/directions?tenant_id=${tenantId}`, { method: "POST", body: JSON.stringify({ origin: { latitude: here.latitude.toFixed(6), longitude: here.longitude.toFixed(6) }, task_id: task.id }) });
        setResult({ ...answer, taskId: task.id, customer: task.customer_name });
      })
      .catch(setProblem)
      .finally(() => setBusy(false));
  }, [tenantId, t]);
  const clear = useCallback(() => { setResult(undefined); setProblem(undefined); }, []);
  return { result, busy, problem, show, clear };
}

type Translate = TFunction;

export function distanceText(t: Translate, metres: number): string {
  if (metres < 1000) return t("directions.metres", { value: Math.max(10, Math.round(metres / 10) * 10) });
  return t("directions.kilometres", { value: (metres / 1000).toFixed(metres < 10_000 ? 1 : 0) });
}

export function durationText(t: Translate, seconds: number): string {
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) return t("directions.minutes", { count: minutes });
  return t("directions.hoursMinutes", { hours: Math.floor(minutes / 60), minutes: minutes % 60 });
}

export function stepText(t: Translate, step: Step, customer: string): string {
  if (step.type === 10) return t("directions.step.10", { customer });
  if (step.type === 7) return step.exit_number ? t("directions.step.roundaboutExit", { exit: step.exit_number }) : t("directions.step.7");
  const known = step.type >= 0 && step.type <= 13;
  const action = t(known ? `directions.step.${step.type}` : "directions.step.6");
  // The street name is isolated so an Arabic name reads correctly inside an English sentence and back.
  return step.name ? `${action} ${t("directions.onto", { name: `⁨${step.name}⁩` })}` : action;
}

