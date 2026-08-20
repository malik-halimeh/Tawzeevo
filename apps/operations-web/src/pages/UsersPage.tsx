import { zodResolver } from "@hookform/resolvers/zod";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { apiRequest } from "../api/client";
import type { SystemUserType, User, UserInput, UserListResponse } from "../api/types";
import { EmptyState, ErrorState, FieldError, LoadingState, PageHeader, Pagination, StatusBadge, SuccessNotice } from "../components/Ui";

interface UserFilters {
  search: string;
  first_name: string;
  last_name: string;
  email: string;
  city: string;
  age: string;
  type: "" | SystemUserType;
}

interface UserFormValues extends UserInput {
  type: SystemUserType;
}

const emptyFilters: UserFilters = { search: "", first_name: "", last_name: "", email: "", city: "", age: "", type: "" };

function userQueryString(filters: UserFilters, page: number): string {
  const params = new URLSearchParams({ page: String(page), limit: "10" });
  (Object.keys(filters) as (keyof UserFilters)[]).forEach((key) => {
    const value = filters[key];
    if (value) params.set(key, value);
  });
  return params.toString();
}

function UserForm({ user, onClose }: { user: User | undefined; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [requestError, setRequestError] = useState<unknown>();
  const schema = z.object({
    first_name: z.string().trim().min(1, t("validation.required")).max(100),
    last_name: z.string().trim().min(1, t("validation.required")).max(100),
    email: z.string().trim().email(t("validation.email")),
    phone: z.string().trim().min(1, t("validation.required")).max(64),
    city: z.string().trim().min(1, t("validation.required")).max(120),
    age: z.number().int().min(1, t("validation.age")).max(120, t("validation.age")),
    password: user
      ? z.union([z.literal(""), z.string().min(10, t("validation.passwordLength")).max(128)])
      : z.string().min(10, t("validation.passwordLength")).max(128),
    type: z.enum(["admin", "client"]),
  });
  const { formState: { errors, isSubmitting }, handleSubmit, register, reset } = useForm<UserFormValues>({ resolver: zodResolver(schema) });

  useEffect(() => {
    reset({
      first_name: user?.first_name ?? "",
      last_name: user?.last_name ?? "",
      email: user?.email ?? "",
      phone: user?.phone ?? "",
      city: user?.city ?? "",
      age: user?.age ?? 18,
      password: "",
      type: user?.type ?? "client",
    });
  }, [reset, user]);

  const onSubmit = async (values: UserFormValues) => {
    setRequestError(undefined);
    const payload = user && !values.password ? { ...values, password: undefined } : values;
    try {
      await apiRequest<User>(user ? `/users/${user.id}` : "/users", {
        method: user ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
      onClose();
    } catch (error) {
      setRequestError(error);
    }
  };

  return (
    <section aria-labelledby="user-form-title" className="content-card side-form">
      <div className="side-form-header"><div><p className="section-kicker">{t(user ? "users.editKicker" : "users.createKicker")}</p><h2 id="user-form-title">{t(user ? "users.editTitle" : "users.createTitle")}</h2></div><button aria-label={t("common.close")} className="icon-button" onClick={onClose} type="button">×</button></div>
      {requestError ? <ErrorState error={requestError} /> : null}
      <form className="form-grid" onSubmit={(event) => void handleSubmit(onSubmit)(event)}>
        <label className="field"><span>{t("fields.firstName")}</span><input {...register("first_name")} /><FieldError message={errors.first_name?.message} /></label>
        <label className="field"><span>{t("fields.lastName")}</span><input {...register("last_name")} /><FieldError message={errors.last_name?.message} /></label>
        <label className="field field-wide"><span>{t("fields.email")}</span><input type="email" {...register("email")} /><FieldError message={errors.email?.message} /></label>
        <label className="field"><span>{t("fields.phone")}</span><input dir="ltr" type="tel" {...register("phone")} /><FieldError message={errors.phone?.message} /></label>
        <label className="field"><span>{t("fields.city")}</span><input {...register("city")} /><FieldError message={errors.city?.message} /></label>
        <label className="field"><span>{t("fields.age")}</span><input type="number" {...register("age", { valueAsNumber: true })} /><FieldError message={errors.age?.message} /></label>
        <label className="field"><span>{t("fields.role")}</span><select {...register("type")}><option value="client">{t("roles.client")}</option><option value="admin">{t("roles.platformAdmin")}</option></select><FieldError message={errors.type?.message} /></label>
        <label className="field field-wide"><span>{t(user ? "users.newPassword" : "fields.password")}</span><input autoComplete="new-password" type="password" {...register("password")} />{user ? <small>{t("users.passwordOptional")}</small> : null}<FieldError message={errors.password?.message} /></label>
        <div className="form-actions field-wide"><button className="button button-secondary" onClick={onClose} type="button">{t("common.cancel")}</button><button className="button" disabled={isSubmitting} type="submit">{isSubmitting ? t("common.saving") : t(user ? "common.saveChanges" : "users.createAction")}</button></div>
      </form>
    </section>
  );
}

export function UsersPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<UserFilters>(emptyFilters);
  const [draftFilters, setDraftFilters] = useState<UserFilters>(emptyFilters);
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<User | "create">();
  const [notice, setNotice] = useState<string>();
  const users = useQuery({
    queryKey: ["users", filters, page],
    queryFn: () => apiRequest<UserListResponse>(`/users?${userQueryString(filters, page)}`),
    placeholderData: keepPreviousData,
  });
  const removeUser = useMutation({
    mutationFn: (id: string) => apiRequest<void>(`/users/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      setNotice(t("users.deleted"));
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
  });

  const applyFilters = (event: React.FormEvent) => {
    event.preventDefault();
    setPage(1);
    setFilters(draftFilters);
  };
  const clearFilters = () => {
    setDraftFilters(emptyFilters);
    setFilters(emptyFilters);
    setPage(1);
  };
  const confirmDelete = (user: User) => {
    if (window.confirm(t("users.confirmDelete", { name: `${user.first_name} ${user.last_name}` }))) {
      removeUser.mutate(user.id);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader eyebrow={t("users.eyebrow")} title={t("users.title")} description={t("users.description")} actions={<button className="button" onClick={() => setEditor("create")} type="button">{t("users.add")}</button>} />
      {notice ? <SuccessNotice>{notice}</SuccessNotice> : null}
      {removeUser.error ? <ErrorState error={removeUser.error} /> : null}
      <form className="filter-panel" onSubmit={applyFilters}>
        <label className="field filter-search"><span>{t("common.search")}</span><input value={draftFilters.search} onChange={(event) => setDraftFilters({ ...draftFilters, search: event.target.value })} placeholder={t("users.searchPlaceholder")} /></label>
        <label className="field"><span>{t("fields.firstName")}</span><input value={draftFilters.first_name} onChange={(event) => setDraftFilters({ ...draftFilters, first_name: event.target.value })} /></label>
        <label className="field"><span>{t("fields.lastName")}</span><input value={draftFilters.last_name} onChange={(event) => setDraftFilters({ ...draftFilters, last_name: event.target.value })} /></label>
        <label className="field"><span>{t("fields.email")}</span><input value={draftFilters.email} onChange={(event) => setDraftFilters({ ...draftFilters, email: event.target.value })} /></label>
        <label className="field"><span>{t("fields.city")}</span><input value={draftFilters.city} onChange={(event) => setDraftFilters({ ...draftFilters, city: event.target.value })} /></label>
        <label className="field"><span>{t("fields.age")}</span><input min="1" max="120" type="number" value={draftFilters.age} onChange={(event) => setDraftFilters({ ...draftFilters, age: event.target.value })} /></label>
        <label className="field"><span>{t("fields.role")}</span><select value={draftFilters.type} onChange={(event) => setDraftFilters({ ...draftFilters, type: event.target.value as UserFilters["type"] })}><option value="">{t("common.all")}</option><option value="client">{t("roles.client")}</option><option value="admin">{t("roles.platformAdmin")}</option></select></label>
        <div className="filter-actions"><button className="button button-secondary" onClick={clearFilters} type="button">{t("common.clear")}</button><button className="button" type="submit">{t("common.apply")}</button></div>
      </form>
      {editor ? <UserForm user={editor === "create" ? undefined : editor} onClose={() => setEditor(undefined)} /> : null}
      {users.isPending ? <LoadingState /> : null}
      {users.error ? <ErrorState error={users.error} /> : null}
      {users.data && !users.data.users.length ? <EmptyState title={t("users.emptyTitle")} body={t("users.emptyBody")} /> : null}
      {users.data?.users.length ? (
        <section className="table-card">
          <div className="table-summary">{t("users.resultCount", { count: users.data.total })}</div>
          <div className="table-scroll"><table><thead><tr><th>{t("users.person")}</th><th>{t("fields.city")}</th><th>{t("fields.age")}</th><th>{t("fields.role")}</th><th><span className="sr-only">{t("common.actions")}</span></th></tr></thead><tbody>{users.data.users.map((user) => <tr key={user.id}><td><strong>{user.first_name} {user.last_name}</strong><span>{user.email}</span><small dir="ltr">{user.phone}</small></td><td>{user.city}</td><td>{user.age}</td><td><StatusBadge value={user.type} /></td><td><div className="row-actions"><button onClick={() => setEditor(user)} type="button">{t("common.edit")}</button><button className="danger-link" disabled={removeUser.isPending} onClick={() => confirmDelete(user)} type="button">{t("common.delete")}</button></div></td></tr>)}</tbody></table></div>
          <Pagination page={users.data.page} totalPages={users.data.total_pages} onPage={setPage} />
        </section>
      ) : null}
    </div>
  );
}
