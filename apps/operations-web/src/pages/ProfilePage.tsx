import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { z } from "zod";

import { apiRequest } from "../api/client";
import type { User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, FieldError, PageHeader, SuccessNotice } from "../components/Ui";

interface ProfileValues {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  city: string;
  age: number;
  password: string;
}

export function ProfilePage() {
  const { t } = useTranslation();
  const { endLocalSession, refreshUser, user } = useAuth();
  const navigate = useNavigate();
  const [requestError, setRequestError] = useState<unknown>();
  const [saved, setSaved] = useState(false);
  const schema = z.object({
    first_name: z.string().trim().min(1, t("validation.required")).max(100),
    last_name: z.string().trim().min(1, t("validation.required")).max(100),
    email: z.string().trim().email(t("validation.email")),
    phone: z.string().trim().min(1, t("validation.required")).max(64),
    city: z.string().trim().min(1, t("validation.required")).max(120),
    age: z.number().int().min(1, t("validation.age")).max(120, t("validation.age")),
    password: z.union([z.literal(""), z.string().min(10, t("validation.passwordLength")).max(128)]),
  });
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm<ProfileValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (!user) return;
    reset({
      first_name: user.first_name,
      last_name: user.last_name,
      email: user.email,
      phone: user.phone,
      city: user.city,
      age: user.age,
      password: "",
    });
  }, [reset, user]);

  const onSubmit = async (values: ProfileValues) => {
    setRequestError(undefined);
    setSaved(false);
    const passwordChanged = Boolean(values.password);
    const payload = passwordChanged ? values : { ...values, password: undefined };
    try {
      await apiRequest<User>("/users/me", { method: "PUT", body: JSON.stringify(payload) });
      if (passwordChanged) {
        endLocalSession();
        void navigate("/login", { replace: true, state: { message: t("profile.passwordChanged") } });
        return;
      }
      await refreshUser();
      setSaved(true);
    } catch (error) {
      setRequestError(error);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={t("profile.eyebrow")}
        title={t("profile.title")}
        description={t("profile.description")}
      />
      <section className="content-card profile-card">
        <div className="identity-strip">
          <span className="avatar" aria-hidden="true">{user?.first_name[0]}{user?.last_name[0]}</span>
          <div><strong>{user?.first_name} {user?.last_name}</strong><span>{t(`roles.${user?.type === "admin" ? "platformAdmin" : "client"}`)}</span></div>
        </div>
        {saved ? <SuccessNotice>{t("profile.saved")}</SuccessNotice> : null}
        {requestError ? <ErrorState error={requestError} /> : null}
        <form className="form-grid" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
          <label className="field"><span>{t("fields.firstName")}</span><input {...register("first_name")} /><FieldError message={errors.first_name?.message} /></label>
          <label className="field"><span>{t("fields.lastName")}</span><input {...register("last_name")} /><FieldError message={errors.last_name?.message} /></label>
          <label className="field field-wide"><span>{t("fields.email")}</span><input type="email" {...register("email")} /><FieldError message={errors.email?.message} /></label>
          <label className="field"><span>{t("fields.phone")}</span><input dir="ltr" type="tel" {...register("phone")} /><FieldError message={errors.phone?.message} /></label>
          <label className="field"><span>{t("fields.city")}</span><input {...register("city")} /><FieldError message={errors.city?.message} /></label>
          <label className="field"><span>{t("fields.age")}</span><input type="number" {...register("age", { valueAsNumber: true })} /><FieldError message={errors.age?.message} /></label>
          <label className="field field-wide"><span>{t("profile.newPassword")}</span><input autoComplete="new-password" placeholder={t("profile.passwordPlaceholder")} type="password" {...register("password")} /><small>{t("profile.passwordHint")}</small><FieldError message={errors.password?.message} /></label>
          <div className="form-actions field-wide"><button className="button" disabled={isSubmitting} type="submit">{isSubmitting ? t("common.saving") : t("common.saveChanges")}</button></div>
        </form>
      </section>
    </div>
  );
}
