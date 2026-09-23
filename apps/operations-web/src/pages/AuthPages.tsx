import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";
import { useForm, type UseFormRegisterReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, Navigate, NavLink, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { apiRequest } from "../api/client";
import type { User, UserInput } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { BrandMark, LanguageButton } from "../components/AppShell";
import { Arrow, Icon, type IconName } from "../components/Icon";
import { RouteMural } from "../components/Illustrations";
import { ErrorState, FieldError } from "../components/Ui";

interface LoginValues {
  email: string;
  password: string;
}

interface RegistrationValues extends UserInput {
  password_confirmation: string;
}

/**
 * The Daylight public-entry frame (docs/design-references/PUBLIC_ENTRY.md): a story panel
 * beside the form. Only presentation lives here; every form keeps its own validation, request,
 * error handling, throttling responses and redirect semantics.
 */
function AuthFrame({
  icon,
  eyebrow,
  title,
  intro,
  wide = false,
  children,
}: {
  icon: IconName;
  eyebrow: string;
  title: string;
  intro: string;
  wide?: boolean;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="entry-page">
      <a className="skip-link" href="#main">{t("skipToContent")}</a>
      <header className="site-header">
        <BrandMark />
        <nav aria-label={t("nav.primary")} className="site-nav">
          <NavLink className="site-nav-link about-link" to="/">{t("nav.home")}</NavLink>
          <LanguageButton />
        </nav>
      </header>
      <main className="signin-layout" id="main" tabIndex={-1}>
        <aside className="signin-story">
          <p className="eyebrow">{t("entry.storyEyebrow")}</p>
          <h2>{t("entry.storyTitle")}</h2>
          <p>{t("entry.storyBody")}</p>
          <RouteMural />
          <div className="story-foot">
            <span><Icon name="invoice" small />{t("entry.storyOrders")}</span>
            <span><Icon name="person" small />{t("entry.storyCustomers")}</span>
            <span><Icon name="van" small />{t("entry.storyDeliveries")}</span>
          </div>
        </aside>
        <section aria-labelledby="entry-title" className={`signin-panel${wide ? " wide" : ""}`}>
          <div className="form-intro">
            <span className="welcome-icon" aria-hidden="true"><Icon name={icon} /></span>
            <p className="eyebrow">{eyebrow}</p>
            <h1 id="entry-title">{title}</h1>
            <p>{intro}</p>
          </div>
          {children}
        </section>
      </main>
      <footer className="site-footer">
        <span>{t("landing.footer")}</span>
        <div><Link to="/stats">{t("nav.statistics")}</Link></div>
      </footer>
    </div>
  );
}

type FieldInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & { field: UseFormRegisterReturn };

/** A labelled input with a leading icon; the error text is announced and linked to the input. */
function EntryField({ label, icon, error, wide = false, field, ...input }: { label: string; icon?: IconName | undefined; error?: string | undefined; wide?: boolean } & FieldInputProps) {
  const id = useId();
  return (
    <div className={`field entry-field${wide ? " field-wide" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <div className={`input-shell${icon ? " with-icon" : ""}`}>
        {icon ? <Icon name={icon} small /> : null}
        <input aria-describedby={error ? `${id}-error` : undefined} aria-invalid={error ? true : undefined} id={id} {...input} {...field} />
      </div>
      <FieldError id={`${id}-error`} message={error} />
    </div>
  );
}

/** A password input with a labelled visibility toggle (pressed state, changing name). */
function PasswordField({ label, error, field, ...input }: { label: string; error?: string | undefined } & FieldInputProps) {
  const { t } = useTranslation();
  const id = useId();
  const [visible, setVisible] = useState(false);
  return (
    <div className="field entry-field">
      <label htmlFor={id}>{label}</label>
      <div className="input-shell with-icon with-reveal">
        <Icon name="lock" small />
        <input aria-describedby={error ? `${id}-error` : undefined} aria-invalid={error ? true : undefined} id={id} type={visible ? "text" : "password"} {...input} {...field} />
        <button aria-pressed={visible} className="reveal" onClick={() => setVisible((current) => !current)} type="button">
          <Icon name={visible ? "eyeOff" : "eye"} small />
          <span className="sr-only">{t(visible ? "entry.hidePassword" : "entry.showPassword")}</span>
        </button>
      </div>
      <FieldError id={`${id}-error`} message={error} />
    </div>
  );
}

function CustomerNote() {
  const { t } = useTranslation();
  return (
    <div className="customer-note">
      <Icon name="shop" />
      <p><strong>{t("entry.customerTitle")}</strong><span>{t("entry.customerBody")}</span></p>
    </div>
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
  // The guard that sent the visitor here remembers the requested path; it wins over the default
  // destination both after the sign-in request and on the authenticated re-render.
  const requestedPath = (location.state as { from?: string } | null)?.from;
  const destinationFor = (type: User["type"]) => requestedPath ?? (type === "admin" ? "/admin" : "/workspace");

  if (status === "authenticated" && user) {
    return <Navigate replace to={destinationFor(user.type)} />;
  }

  const message = (location.state as { message?: string } | null)?.message;
  const onSubmit = async (values: LoginValues) => {
    setRequestError(undefined);
    try {
      const currentUser = await login(values.email, values.password);
      void navigate(destinationFor(currentUser.type), { replace: true });
    } catch (error) {
      setRequestError(error);
    }
  };

  return (
    <AuthFrame eyebrow={t("entry.workspace")} icon="sun" intro={t("login.intro")} title={t("login.title")}>
      {message ? <div className="notice notice-success" role="status">{message}</div> : null}
      {requestError ? <ErrorState error={requestError} /> : null}
      <form aria-busy={isSubmitting} className="entry-form" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
        <EntryField autoComplete="email" dir="ltr" error={errors.email?.message} field={register("email")} icon="email" inputMode="email" label={t("fields.email")} type="email" />
        <PasswordField autoComplete="current-password" dir="ltr" error={errors.password?.message} field={register("password")} label={t("fields.password")} />
        <div className="form-options"><Link to="/forgot-password">{t("recovery.forgotLink")}</Link></div>
        <button className="button button-arrow submit" disabled={isSubmitting} type="submit">
          {isSubmitting ? t("common.signingIn") : t("nav.login")}<Arrow />
        </button>
      </form>
      <p className="register-note">{t("login.noAccount")} <Link to="/register">{t("login.createAccount")}</Link></p>
      <CustomerNote />
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
    <AuthFrame eyebrow={t("register.eyebrow")} icon="person" intro={t("register.intro")} title={t("register.formTitle")} wide>
      {requestError ? <ErrorState error={requestError} /> : null}
      <form aria-busy={isSubmitting} className="entry-form form-grid" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
        <EntryField autoComplete="given-name" error={errors.first_name?.message} field={register("first_name")} label={t("fields.firstName")} />
        <EntryField autoComplete="family-name" error={errors.last_name?.message} field={register("last_name")} label={t("fields.lastName")} />
        <EntryField autoComplete="email" dir="ltr" error={errors.email?.message} field={register("email")} icon="email" inputMode="email" label={t("fields.email")} type="email" wide />
        <EntryField autoComplete="tel" dir="ltr" error={errors.phone?.message} field={register("phone")} icon="phone" label={t("fields.phone")} type="tel" />
        <EntryField autoComplete="address-level2" error={errors.city?.message} field={register("city")} label={t("fields.city")} />
        <EntryField error={errors.age?.message} field={register("age", { valueAsNumber: true })} inputMode="numeric" label={t("fields.age")} type="number" />
        <span className="form-spacer" aria-hidden="true" />
        <PasswordField autoComplete="new-password" dir="ltr" error={errors.password?.message} field={register("password")} label={t("fields.password")} />
        <PasswordField autoComplete="new-password" dir="ltr" error={errors.password_confirmation?.message} field={register("password_confirmation")} label={t("fields.confirmPassword")} />
        <button className="button button-arrow submit field-wide" disabled={isSubmitting} type="submit">
          {isSubmitting ? t("common.creatingAccount") : t("register.action")}<Arrow />
        </button>
      </form>
      <p className="register-note">{t("register.hasAccount")} <Link to="/login">{t("nav.login")}</Link></p>
      <CustomerNote />
    </AuthFrame>
  );
}

/** Password recovery (D-077): the answer is the same whether or not the address exists. */
export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [requestError, setRequestError] = useState<unknown>();
  const [sent, setSent] = useState(false);
  const schema = z.object({ email: z.string().trim().email(t("validation.email")) });
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<{ email: string }>({ resolver: zodResolver(schema) });
  const onSubmit = async (values: { email: string }) => {
    setRequestError(undefined);
    try {
      await apiRequest<{ status: string }>("/api/v1/auth/password/forgot", { method: "POST", authenticated: false, body: JSON.stringify(values) });
      setSent(true);
    } catch (error) {
      setRequestError(error);
    }
  };
  return (
    <AuthFrame eyebrow={t("recovery.eyebrow")} icon="lock" intro={t("recovery.intro")} title={t("recovery.title")}>
      {requestError ? <ErrorState error={requestError} /> : null}
      {sent ? <div className="notice notice-success" role="status">{t("recovery.sent")}</div> : (
        <form aria-busy={isSubmitting} className="entry-form" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
          <EntryField autoComplete="email" dir="ltr" error={errors.email?.message} field={register("email")} icon="email" inputMode="email" label={t("fields.email")} type="email" />
          <button className="button button-arrow submit" disabled={isSubmitting} type="submit">{t("recovery.send")}<Arrow /></button>
        </form>
      )}
      <Link className="back-signin" to="/login"><Arrow back small />{t("recovery.backToLogin")}</Link>
    </AuthFrame>
  );
}

/** The one-time token arrives in the URL fragment (never sent to a server by the browser). */
export function ResetPasswordPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [requestError, setRequestError] = useState<unknown>();
  const token = window.location.hash.replace(/^#/, "");
  const schema = z
    .object({
      password: z.string().min(10, t("validation.passwordLength")).max(128),
      password_confirmation: z.string(),
    })
    .refine((values) => values.password === values.password_confirmation, { path: ["password_confirmation"], message: t("validation.passwordMatch") });
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<{ password: string; password_confirmation: string }>({ resolver: zodResolver(schema) });
  const onSubmit = async (values: { password: string; password_confirmation: string }) => {
    setRequestError(undefined);
    try {
      await apiRequest<undefined>("/api/v1/auth/password/reset", { method: "POST", authenticated: false, body: JSON.stringify({ token, password: values.password }) });
      history.replaceState(null, "", window.location.pathname);
      void navigate("/login", { replace: true, state: { message: t("recovery.done") } });
    } catch (error) {
      setRequestError(error);
    }
  };
  return (
    <AuthFrame eyebrow={t("recovery.eyebrow")} icon="lock" intro={t("recovery.resetIntro")} title={t("recovery.resetTitle")}>
      {!token ? <div className="notice notice-error" role="alert">{t("recovery.missingToken")}</div> : null}
      {requestError ? <ErrorState error={requestError} /> : null}
      <form aria-busy={isSubmitting} className="entry-form" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
        <PasswordField autoComplete="new-password" dir="ltr" error={errors.password?.message} field={register("password")} label={t("fields.password")} />
        <PasswordField autoComplete="new-password" dir="ltr" error={errors.password_confirmation?.message} field={register("password_confirmation")} label={t("fields.confirmPassword")} />
        <button className="button button-arrow submit" disabled={isSubmitting || !token} type="submit">{t("recovery.resetAction")}<Arrow /></button>
      </form>
      <Link className="back-signin" to="/forgot-password"><Arrow back small />{t("recovery.requestAgain")}</Link>
    </AuthFrame>
  );
}
