import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

const contactSchema = z.object({ email: z.email() });
type ContactForm = z.infer<typeof contactSchema>;

const foundations = ["api", "database", "tenant"] as const;

export function App() {
  const { i18n, t } = useTranslation();
  const {
    formState: { errors, isSubmitSuccessful },
    handleSubmit,
    register,
  } = useForm<ContactForm>({ resolver: zodResolver(contactSchema) });

  const switchLanguage = async () => {
    const language = i18n.language === "ar" ? "en" : "ar";
    await i18n.changeLanguage(language);
    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  };

  return (
    <main className="shell">
      <nav aria-label="Primary navigation">
        <a className="brand" href="/">{t("brand")}</a>
        <button className="language" onClick={() => void switchLanguage()} type="button">
          {t("language")}
        </button>
      </nav>

      <section className="hero">
        <p className="eyebrow">{t("eyebrow")}</p>
        <h1>{t("heading")}</h1>
        <p className="lede">{t("body")}</p>
      </section>

      <section aria-labelledby="foundation-heading" className="panel">
        <h2 id="foundation-heading">{t("foundation")}</h2>
        <ul>
          {foundations.map((item) => (
            <li key={item}>
              <span>{t(item)}</span>
              <strong>{t("ready")}</strong>
            </li>
          ))}
        </ul>
      </section>

      <form className="panel form" onSubmit={(event) => void handleSubmit(() => undefined)(event)}>
        <label htmlFor="email">{t("email")}</label>
        <input id="email" type="email" {...register("email")} />
        {errors.email ? <p role="alert">{errors.email.message}</p> : null}
        <button type="submit">{t("validate")}</button>
        {isSubmitSuccessful ? <p role="status">{t("valid")}</p> : null}
      </form>
    </main>
  );
}
