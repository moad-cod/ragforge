"use client";

import {zodResolver} from "@hookform/resolvers/zod";
import {LoaderCircle} from "lucide-react";
import {useForm} from "react-hook-form";
import {z} from "zod";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import type {Chunker, Organization} from "@/lib/types";

const schema = z.object({name: z.string().trim().min(2, "Enter at least 2 characters").max(120), organization_id: z.string(), chunker: z.string()});
export type ProjectFormValues = z.infer<typeof schema>;

export function ProjectForm({organizations, chunkers, isPending, submitLabel = "Create project", initialName = "", onCancel, onSubmit}: {
  organizations?: Organization[];
  chunkers?: Chunker[];
  isPending?: boolean;
  submitLabel?: string;
  initialName?: string;
  onCancel: () => void;
  onSubmit: (values: ProjectFormValues) => void;
}) {
  const {register, handleSubmit, formState: {errors}} = useForm<ProjectFormValues>({resolver: zodResolver(schema), defaultValues: {name: initialName, organization_id: "", chunker: "paragraph"}});
  return <form className="mt-6 space-y-4" onSubmit={handleSubmit(onSubmit)}>
    <label className="block"><span className="mb-2 block text-xs font-medium">Project name</span><Input autoFocus placeholder="Product knowledge base" {...register("name")} />{errors.name ? <span className="mt-1.5 block text-xs text-red-300">{errors.name.message}</span> : null}</label>
    {organizations ? <label className="block"><span className="mb-2 block text-xs font-medium">Organization</span><select className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 text-sm outline-none focus:border-[var(--accent)]" {...register("organization_id")}><option value="">Personal workspace</option>{organizations.map((organization) => <option key={organization.organization_id} value={organization.organization_id}>{organization.name}</option>)}</select></label> : null}
    {chunkers ? <label className="block"><span className="mb-2 block text-xs font-medium">Default chunking strategy</span><select className="h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--surface-muted)] px-3 text-sm outline-none focus:border-[var(--accent)]" {...register("chunker")}>{chunkers.filter((item) => item.id !== "multimodal").map((item) => <option key={item.id} value={item.id}>{item.name}{item.default ? " · Recommended" : ""}</option>)}</select><span className="mt-1.5 block text-[10px] leading-4 text-[#77716a]">Saved as a browser preference and applied to the upload form. The backend stores the chosen strategy on each document version.</span></label> : null}
    <label className="block"><span className="mb-2 block text-xs font-medium">Description <span className="font-normal text-[#77716a]">(not supported by the current API)</span></span><textarea disabled className="min-h-20 w-full resize-none rounded-lg border border-white/[0.06] bg-white/[0.015] px-3 py-2.5 text-sm text-[#5f5952]" placeholder="Project descriptions will be available when backend support is added." /></label>
    <details className="rounded-lg border border-white/[0.08] bg-white/[0.018] p-3"><summary className="cursor-pointer text-xs font-medium">Advanced configuration</summary><dl className="mt-3 grid gap-3 text-[10px] sm:grid-cols-2"><div><dt className="text-[#77716a]">Embedding model</dt><dd className="mono mt-1 text-[#c9c1b7]">BAAI/bge-small-en-v1.5</dd></div><div><dt className="text-[#77716a]">Retrieval</dt><dd className="mt-1 text-[#c9c1b7]">Hybrid dense + sparse</dd></div></dl><p className="mt-3 text-[9px] leading-4 text-[#5f5952]">These values reflect the backend defaults and are read-only because project-level configuration is not currently exposed.</p></details>
    <div className="flex justify-end gap-2 pt-2"><Button variant="secondary" onClick={onCancel}>Cancel</Button><Button type="submit" disabled={isPending}>{isPending ? <LoaderCircle className="size-4 animate-spin" /> : null}{submitLabel}</Button></div>
  </form>;
}
