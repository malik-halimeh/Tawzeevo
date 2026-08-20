import { zodResolver } from "@hookform/resolvers/zod";
import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { apiRequest } from "../api/client";
import type { User, UserInput } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { BrandMark, LanguageButton } from "../components/AppShell";
import { ErrorState, FieldError } from "../components/Ui";

interface LoginValues {
  email: string;
  password: string;
}

interface RegistrationValues extends UserInput {
  password_confirmation: string;
}

function AuthFrame({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  children: ReactNode;
}) {
  return (
    <main className="auth-page">
      <header className="auth-header">
        <BrandMark />
        <LanguageButton />
      </header>
      <div className="auth-layout">
        <section className="auth-intro">
          <div className="auth-route-map" aria-hidden="true">
            <span /><span /><span /><span />
          </div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{intro}</p>
        </section>
        <section className="auth-card">{children}</section>
      </div>
    </main>
  );
}

export function LoginPage() {
  const { t } = useTranslation();
  const { login, status, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [requestError, setRequestError] = useState<unknown>();
  const schema = z.object({
    email: z.string().trim().email(t("validation.email")),
    password: z.string().min(1, t("validation.required")),
  });
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<LoginValues>({ resolver: zodResolver(schema) });

  if (status === "authenticated" && user) {
    return <Navigate replace to={user.type === "admin" ? "/admin" : "/workspace"} />;
  }

  const message = (location.state as { message?: string } | null)?.message;
  const onSubmit = async (values: LoginValues) => {
    setRequestError(undefined);
    try {
      const currentUser = await login(values.email, values.password);
      const requestedPath = (location.state as { from?: string } | null)?.from;
      const destination = requestedPath ?? (currentUser.type === "admin" ? "/admin" : "/workspace");
      void navigate(destination, { replace: true });
    } catch (error) {
      setRequestError(error);
    }
  };

  return (
    <AuthFrame
      eyebrow={t("login.eyebrow")}
      title={t("login.title")}
      intro={t("login.intro")}
    >
      <div className="form-heading">
        <h2>{t("login.formTitle")}</h2>
        <p>{t("login.noAccount")} <Link to="/register">{t("login.createAccount")}</Link></p>
      </div>
      {message ? <div className="notice notice-success" role="status">{message}</div> : null}
      {requestError ? <ErrorState error={requestError} /> : null}
      <form className="form-stack" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
        <label className="field">
          <span>{t("fields.email")}</span>
          <input autoComplete="email" type="email" {...register("email")} />
          <FieldError message={errors.email?.message} />
        </label>
        <label className="field">
          <span>{t("fields.password")}</span>
          <input autoComplete="current-password" type="password" {...register("password")} />
          <FieldError message={errors.password?.message} />
        </label>
        <button className="button" disabled={isSubmitting} type="submit">
          {isSubmitting ? t("common.signingIn") : t("nav.login")}
        </button>
      </form>
      <Link className="back-link" to="/stats">{t("login.viewStatistics")}</Link>
    </AuthFrame>
  );
}

export function RegisterPage() {
  const { t } = useTranslation();
  const { status, user } = useAuth();
  const navigate = useNavigate();
  const [requestError, setRequestError] = useState<unknown>();
  const schema = z
    .object({
      first_name: z.string().trim().min(1, t("validation.required")).max(100),
      last_name: z.string().trim().min(1, t("validation.required")).max(100),
      email: z.string().trim().email(t("validation.email")),
      phone: z.string().trim().min(1, t("validation.required")).max(64),
      city: z.string().trim().min(1, t("validation.required")).max(120),
      age: z.number().int().min(1, t("validation.age")).max(120, t("validation.age")),
      password: z.string().min(10, t("validation.passwordLength")).max(128),
      password_confirmation: z.string(),
    })
    .refine((values) => values.password === values.password_confirmation, {
      path: ["password_confirmation"],
      message: t("validation.passwordMatch"),
    });
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<RegistrationValues>({ resolver: zodResolver(schema) });

  if (status === "authenticated" && user) {
    return <Navigate replace to={user.type === "admin" ? "/admin" : "/workspace"} />;
  }

  const onSubmit = async (registration: RegistrationValues) => {
    setRequestError(undefined);
    const values: UserInput = {
      first_name: registration.first_name,
      last_name: registration.last_name,
      email: registration.email,
      phone: registration.phone,
      city: registration.city,
      age: registration.age,
      password: registration.password,
    };
    try {
      await apiRequest<User>("/register", {
        method: "POST",
        authenticated: false,
        body: JSON.stringify(values),
      });
      void navigate("/login", {
        replace: true,
        state: { message: t("register.success") },
      });
    } catch (error) {
      setRequestError(error);
    }
  };

  return (
    <AuthFrame
      eyebrow={t("register.eyebrow")}
      title={t("register.title")}
      intro={t("register.intro")}
    >
      <div className="form-heading">
        <h2>{t("register.formTitle")}</h2>
        <p>{t("register.hasAccount")} <Link to="/login">{t("nav.login")}</Link></p>
      </div>
      {requestError ? <ErrorState error={requestError} /> : null}
      <form className="form-grid" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
        <label className="field">
          <span>{t("fields.firstName")}</span>
          <input autoComplete="given-name" {...register("first_name")} />
          <FieldError message={errors.first_name?.message} />
        </label>
        <label className="field">
          <span>{t("fields.lastName")}</span>
          <input autoComplete="family-name" {...register("last_name")} />
          <FieldError message={errors.last_name?.message} />
        </label>
        <label className="field field-wide">
          <span>{t("fields.email")}</span>
          <input autoComplete="email" type="email" {...register("email")} />
          <FieldError message={errors.email?.message} />
        </label>
        <label className="field">
          <span>{t("fields.phone")}</span>
          <input autoComplete="tel" dir="ltr" type="tel" {...register("phone")} />
          <FieldError message={errors.phone?.message} />
        </label>
        <label className="field">
          <span>{t("fields.city")}</span>
          <input autoComplete="address-level2" {...register("city")} />
          <FieldError message={errors.city?.message} />
        </label>
        <label className="field">
          <span>{t("fields.age")}</span>
          <input inputMode="numeric" type="number" {...register("age", { valueAsNumber: true })} />
          <FieldError message={errors.age?.message} />
        </label>
        <span className="form-spacer" aria-hidden="true" />
        <label className="field">
          <span>{t("fields.password")}</span>
          <input autoComplete="new-password" type="password" {...register("password")} />
          <FieldError message={errors.password?.message} />
        </label>
        <label className="field">
          <span>{t("fields.confirmPassword")}</span>
          <input autoComplete="new-password" type="password" {...register("password_confirmation")} />
          <FieldError message={errors.password_confirmation?.message} />
        </label>
        <button className="button field-wide" disabled={isSubmitting} type="submit">
          {isSubmitting ? t("common.creatingAccount") : t("register.action")}
        </button>
      </form>
    </AuthFrame>
  );
}
