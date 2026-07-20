"use client";

import {useQuery} from "@tanstack/react-query";
import {
  BarChart3,
  Bell,
  Blocks,
  ChevronDown,
  CircleHelp,
  Clock3,
  Command,
  FileStack,
  FolderKanban,
  LogOut,
  Menu,
  Moon,
  Network,
  Search,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {useEffect, useMemo, useState} from "react";
import {apiFetch, authFetch} from "@/lib/api";
import type {Project, User} from "@/lib/types";
import {cn, initials} from "@/lib/utils";

function projectIdFromPath(pathname: string) {
  const match = pathname.match(/^\/projects\/([^/]+)/);
  return match?.[1] ?? null;
}

export function AppShell({children}: {children: React.ReactNode}) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [projectPickerOpen, setProjectPickerOpen] = useState(false);
  const projectId = projectIdFromPath(pathname);
  const {data: user} = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/auth/me"),
  });
  const {data: projects = []} = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<Project[]>("/projects/"),
  });
  const selectedProject = useMemo(
    () => projects.find((project) => project.project_id === projectId),
    [projectId, projects],
  );

  const nav = projectId
    ? [
        {href: `/projects/${projectId}/documents`, label: "Documents", icon: Files},
        {href: `/projects/${projectId}/chat`, label: "Ask RAGForge", icon: MessageSquareText},
        {href: `/projects/${projectId}/history`, label: "Query history", icon: History},
      ]
    : [];

  async function logout() {
    await authFetch("/logout");
    router.replace("/login");
    router.refresh();
  }

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-20 items-center justify-between px-5">
        <Brand inverse />
        <button
          className="text-slate-400 lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        >
          <X className="size-5" />
        </button>
      </div>

      <div className="px-4">
        <Link
          href="/projects"
          className={cn(
            "flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition",
            pathname === "/projects"
              ? "bg-white/10 text-white"
              : "text-slate-400 hover:bg-white/5 hover:text-white",
          )}
          onClick={() => setMobileOpen(false)}
        >
          <FolderKanban className="size-4.5" />
          All projects
        </Link>
      </div>

      <div className="relative mx-4 mt-5">
        <button
          className="flex w-full items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3 text-left"
          onClick={() => setProjectPickerOpen((open) => !open)}
        >
          <span className="min-w-0">
            <span className="block text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Active project
            </span>
            <span className="mt-1 block truncate text-sm font-medium text-slate-200">
              {selectedProject?.name ?? "Choose a project"}
            </span>
          </span>
          <ChevronDown className="size-4 text-slate-500" />
        </button>
        {projectPickerOpen ? (
          <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-30 max-h-72 overflow-auto rounded-xl border border-slate-700 bg-[#172236] p-1.5 shadow-2xl">
            {projects.map((project) => (
              <Link
                key={project.project_id}
                href={`/projects/${project.project_id}/documents`}
                className="block truncate rounded-lg px-3 py-2.5 text-sm text-slate-300 hover:bg-white/10 hover:text-white"
                onClick={() => {
                  setProjectPickerOpen(false);
                  setMobileOpen(false);
                }}
              >
                {project.name}
              </Link>
            ))}
            <Link
              href="/projects"
              className="mt-1 flex items-center gap-2 rounded-lg border-t border-white/10 px-3 py-2.5 text-sm font-medium text-indigo-300 hover:bg-white/10"
              onClick={() => {
                setProjectPickerOpen(false);
                setMobileOpen(false);
              }}
            >
              <Plus className="size-4" />
              New project
            </Link>
          </div>
        ) : null}
      </div>

      {nav.length ? (
        <nav className="mt-5 space-y-1 px-4">
          {nav.map(({href, label, icon: Icon}) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition",
                pathname === href
                  ? "bg-[var(--accent)] text-white shadow-lg shadow-indigo-950/20"
                  : "text-slate-400 hover:bg-white/5 hover:text-white",
              )}
              onClick={() => setMobileOpen(false)}
            >
              <Icon className="size-4.5" />
              {label}
            </Link>
          ))}
        </nav>
      ) : null}

      <div className="mt-auto border-t border-white/10 p-4">
        <div className="flex items-center gap-3 rounded-xl p-2">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-indigo-400/15 text-xs font-bold text-indigo-200">
            {user ? initials(user.full_name, user.email) : "RF"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-200">
              {user?.full_name || "RAGForge user"}
            </p>
            <p className="truncate text-xs text-slate-500">{user?.email}</p>
          </div>
          <button
            aria-label="Sign out"
            className="rounded-lg p-2 text-slate-500 hover:bg-white/5 hover:text-white"
            onClick={logout}
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 bg-[var(--surface-dark)] lg:block">
        {sidebar}
      </aside>
      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative h-full w-[85%] max-w-72 bg-[var(--surface-dark)]">
            {sidebar}
          </aside>
        </div>
      ) : null}
      <div className="lg:pl-72">
        <div className="sticky top-0 z-20 flex h-16 items-center border-b border-[var(--border)] bg-white/90 px-4 backdrop-blur lg:hidden">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="size-5" />
          </Button>
          <span className="ml-2 truncate text-sm font-semibold">
            {selectedProject?.name ?? "RAGForge"}
          </span>
        </div>
        <main className="mx-auto min-h-screen max-w-[1500px] px-5 py-7 sm:px-8 sm:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}
