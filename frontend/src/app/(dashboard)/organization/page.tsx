"use client";

import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {Building2, LoaderCircle, Pencil, Plus, Trash2} from "lucide-react";
import {useState} from "react";
import {toast} from "sonner";
import {ConfirmDeleteDialog} from "@/components/confirm-delete-dialog";
import {PageHeader} from "@/components/page-header";
import {Button} from "@/components/ui/button";
import {Dialog} from "@/components/ui/dialog";
import {EmptyState} from "@/components/ui/empty-state";
import {ErrorState} from "@/components/ui/error-state";
import {Input} from "@/components/ui/input";
import {LoadingState} from "@/components/ui/loading-state";
import {apiFetch} from "@/lib/api";
import type {Organization, User} from "@/lib/types";
import {relativeTime} from "@/lib/utils";

export default function OrganizationPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Organization | "new" | null>(null);
  const [deleting, setDeleting] = useState<Organization | null>(null);
  const [name, setName] = useState("");
  const organizations = useQuery({queryKey: ["organizations"], queryFn: () => apiFetch<Organization[]>("/organizations/")});
  const user = useQuery({queryKey: ["me"], queryFn: () => apiFetch<User>("/auth/me")});
  const save = useMutation({mutationFn: () => editing === "new" ? apiFetch<Organization>("/organizations/", {method: "POST", body: JSON.stringify({name})}) : apiFetch<Organization>(`/organizations/${editing?.organization_id}`, {method: "PATCH", body: JSON.stringify({name})}), onSuccess: async () => {await queryClient.invalidateQueries({queryKey: ["organizations"]}); setEditing(null); setName(""); toast.success("Organization saved");}, onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to save organization")});
  const remove = useMutation({mutationFn: (id: string) => apiFetch(`/organizations/${id}`, {method: "DELETE"}), onSuccess: async () => {await queryClient.invalidateQueries({queryKey: ["organizations"]}); setDeleting(null); toast.success("Organization deleted");}, onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to delete organization")});
  function open(value: Organization | "new") {setEditing(value); setName(value === "new" ? "" : value.name);}
  return <div className="mx-auto max-w-5xl space-y-6"><PageHeader eyebrow="Account" title="Organization settings" description="Create and rename organizations, then choose your active organization from the application top bar." actions={<Button onClick={() => open("new")}><Plus className="size-4" />New organization</Button>} />
    {organizations.isLoading ? <LoadingState label="Loading organizations" rows={3} /> : organizations.isError ? <ErrorState title="Organizations could not be loaded" description="The authenticated organization API returned an error." onRetry={() => void organizations.refetch()} /> : organizations.data?.length ? <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-[#0a1511]">{organizations.data.map((organization) => <article key={organization.organization_id} className="flex flex-col gap-4 border-b border-white/[0.07] p-4 last:border-0 sm:flex-row sm:items-center"><span className="flex size-10 items-center justify-center rounded-xl bg-emerald-400/10 text-emerald-300"><Building2 className="size-5" /></span><div className="min-w-0 flex-1"><h2 className="truncate text-sm font-semibold">{organization.name}</h2><p className="mono mt-1 truncate text-[8px] text-[#53625b]">{organization.organization_id}</p><p className="mt-1 text-[9px] text-[#64736d]">Updated {relativeTime(organization.updated_at)}{user.data?.organization_id === organization.organization_id ? " · Active" : ""}</p></div><div className="flex gap-1"><Button variant="ghost" size="sm" onClick={() => open(organization)}><Pencil className="size-3.5" />Rename</Button><Button variant="ghost" size="sm" className="text-red-300" onClick={() => setDeleting(organization)}><Trash2 className="size-3.5" />Delete</Button></div></article>)}</div> : <EmptyState icon={Building2} title="No organizations yet" description="Projects can remain in your personal workspace, or you can create an organization." action="Create organization" onAction={() => open("new")} />}
    <Dialog open={Boolean(editing)} onClose={() => setEditing(null)} title={editing === "new" ? "Create organization" : "Rename organization"} description="Organization names can be changed without affecting project vector collections."><label className="mt-5 block"><span className="mb-2 block text-xs font-medium">Organization name</span><Input value={name} onChange={(event) => setName(event.target.value)} /></label><div className="mt-6 flex justify-end gap-2"><Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button><Button disabled={name.trim().length < 2 || save.isPending} onClick={() => save.mutate()}>{save.isPending ? <LoaderCircle className="size-4 animate-spin" /> : null}Save organization</Button></div></Dialog>
    {deleting ? <ConfirmDeleteDialog open name={deleting.name} title={`Delete ${deleting.name}?`} consequences="The organization record will be soft-deleted. The current API does not return an impact preview for users or projects, so verify dependencies before continuing." isPending={remove.isPending} onClose={() => setDeleting(null)} onConfirm={() => remove.mutate(deleting.organization_id)} /> : null}
  </div>;
}
