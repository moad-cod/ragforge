"use client";

import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {LoaderCircle, Save, UserRound} from "lucide-react";
import {useState} from "react";
import {toast} from "sonner";
import {PageHeader} from "@/components/page-header";
import {Button} from "@/components/ui/button";
import {ErrorState} from "@/components/ui/error-state";
import {Input} from "@/components/ui/input";
import {LoadingState} from "@/components/ui/loading-state";
import {apiFetch} from "@/lib/api";
import type {Organization, User} from "@/lib/types";
import {initials} from "@/lib/utils";

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const user = useQuery({queryKey: ["me"], queryFn: () => apiFetch<User>("/auth/me")});
  const organizations = useQuery({queryKey: ["organizations"], queryFn: () => apiFetch<Organization[]>("/organizations/")});
  const [name, setName] = useState<string | null>(null); const [email, setEmail] = useState<string | null>(null); const [password, setPassword] = useState(""); const [organizationId, setOrganizationId] = useState<string | null>(null);
  const effectiveName = name ?? user.data?.full_name ?? ""; const effectiveEmail = email ?? user.data?.email ?? ""; const effectiveOrganizationId = organizationId ?? user.data?.organization_id ?? "";
  const save = useMutation({mutationFn: () => apiFetch<User>("/auth/me", {method: "PATCH", body: JSON.stringify({full_name: effectiveName, email: effectiveEmail, organization_id: effectiveOrganizationId, ...(password ? {password} : {})})}), onSuccess: async () => {setName(null); setEmail(null); setOrganizationId(null); setPassword(""); await queryClient.invalidateQueries({queryKey: ["me"]}); toast.success("Profile updated");}, onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to update profile")});
  if (user.isLoading) return <LoadingState label="Loading profile" rows={4} />;
  if (user.isError || !user.data) return <ErrorState title="Profile could not be loaded" description="The current-user endpoint returned an error." onRetry={() => void user.refetch()} />;
  return <div className="mx-auto max-w-4xl space-y-6"><PageHeader eyebrow="Settings" title="Profile" description="Update the identity and organization context associated with your authenticated RAGForge account." />
    <div className="grid gap-5 md:grid-cols-[220px_1fr]"><aside className="rounded-xl border border-white/[0.08] bg-[#0a1511] p-5 text-center"><span className="mx-auto flex size-16 items-center justify-center rounded-2xl bg-emerald-400/10 text-xl font-semibold text-emerald-200">{initials(user.data.full_name, user.data.email)}</span><h2 className="mt-4 text-sm font-semibold">{user.data.full_name || "RAGForge user"}</h2><p className="mt-1 break-all text-[9px] text-[#64736d]">{user.data.email}</p><div className="mt-4 flex items-center justify-center gap-1.5 text-[9px] text-emerald-300"><UserRound className="size-3" />Authenticated account</div></aside><form onSubmit={(event) => {event.preventDefault(); save.mutate();}} className="rounded-xl border border-white/[0.08] bg-[#0a1511] p-5"><div className="grid gap-4 sm:grid-cols-2"><label><span className="mb-2 block text-xs font-medium">Full name</span><Input value={effectiveName} onChange={(event) => setName(event.target.value)} /></label><label><span className="mb-2 block text-xs font-medium">Email</span><Input type="email" value={effectiveEmail} onChange={(event) => setEmail(event.target.value)} /></label><label><span className="mb-2 block text-xs font-medium">Organization</span><select value={effectiveOrganizationId} onChange={(event) => setOrganizationId(event.target.value)} className="h-10 w-full rounded-lg border border-white/[0.08] bg-[var(--surface-muted)] px-3 text-sm"><option value="">Personal workspace</option>{organizations.data?.map((organization) => <option key={organization.organization_id} value={organization.organization_id}>{organization.name}</option>)}</select></label><label><span className="mb-2 block text-xs font-medium">New password <span className="font-normal text-[#64736d]">(optional)</span></span><Input type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="At least 8 characters" /></label></div><div className="mt-6 flex justify-end"><Button type="submit" disabled={save.isPending || !effectiveEmail || (password.length > 0 && password.length < 8)}>{save.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Save className="size-4" />}Save profile</Button></div></form></div>
  </div>;
}
