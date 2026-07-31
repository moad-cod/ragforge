"use client";

import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {
  BarChart3,
  Bell,
  Building2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Command,
  FileStack,
  FolderKanban,
  Home,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  Sparkles,
  UserRound,
  Workflow,
  X,
} from "lucide-react";
import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {useEffect, useMemo, useRef, useState} from "react";
import {toast} from "sonner";
import {apiFetch, authFetch} from "@/lib/api";
import type {Organization, Project, User} from "@/lib/types";
import {cn, initials} from "@/lib/utils";

type NavItem = {label: string; href: string; icon: typeof Home};
type NavGroup = {label: string; items: NavItem[]};

function projectIdFromPath(pathname: string) {
  return pathname.match(/^\/projects\/([^/]+)/)?.[1] ?? null;
}

function navigation(projectId: string | null): NavGroup[] {
  if (projectId) {
    return [
      {
        label: "Project",
        items: [
          {label: "Overview", href: `/projects/${projectId}/overview`, icon: Home},
          {label: "Sources", href: `/projects/${projectId}/sources`, icon: FileStack},
          {label: "Playground", href: `/projects/${projectId}/playground`, icon: Sparkles},
          {label: "Pipelines", href: `/projects/${projectId}/pipelines`, icon: Workflow},
          {label: "Experiments", href: `/projects/${projectId}/experiments`, icon: Clock3},
          {label: "Evaluation", href: `/projects/${projectId}/evaluation`, icon: BarChart3},
          {label: "Settings", href: `/projects/${projectId}/settings`, icon: Settings},
        ],
      },
      {
        label: "Manage",
        items: [
          {label: "All projects", href: "/projects", icon: FolderKanban},
          {label: "Organization", href: "/organization", icon: Building2},
          {label: "Profile", href: "/settings/profile", icon: UserRound},
        ],
      },
    ];
  }
  return [
    {
      label: "Workspace",
      items: [
        {label: "Home", href: "/home", icon: Home},
        {label: "Projects", href: "/projects", icon: FolderKanban},
      ],
    },
    {
      label: "Research",
      items: [
        {label: "Experiments", href: "/experiments", icon: Sparkles},
        {label: "Comparisons", href: "/comparisons", icon: BarChart3},
      ],
    },
    {
      label: "Monitor",
      items: [
        {label: "Runs", href: "/runs", icon: Workflow},
        {label: "Observability", href: "/observability", icon: BarChart3},
      ],
    },
    {
      label: "Manage",
      items: [
        {label: "Organization", href: "/organization", icon: Building2},
        {label: "Settings", href: "/settings/profile", icon: Settings},
      ],
    },
  ];
}

function routeLabel(segment: string, project?: Project) {
  if (segment === project?.project_id) return project.name;
  const labels: Record<string, string> = {
    projects: "Projects",
    sources: "Sources",
    documents: "Sources",
    playground: "Playground",
    pipelines: "Pipelines",
    runs: "Runs",
    history: "Playground history",
    experiments: "Experiments",
    evaluation: "Evaluation",
    comparisons: "Comparisons",
    overview: "Overview",
    observability: "Observability",
    organization: "Organization",
    settings: "Settings",
    profile: "Profile",
  };
  return labels[segment] ?? segment.replaceAll("-", " ");
}

export function AppShell({children}: {children: React.ReactNode}) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const projectId = projectIdFromPath(pathname);
  const [collapsed, setCollapsed] = useState(() => typeof window !== "undefined" && localStorage.getItem("ragforge:sidebar-collapsed") === "true");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const {data: user} = useQuery({queryKey: ["me"], queryFn: () => apiFetch<User>("/auth/me")});
  const {data: projects = []} = useQuery({queryKey: ["projects"], queryFn: () => apiFetch<Project[]>("/projects/")});
  const {data: organizations = []} = useQuery({queryKey: ["organizations"], queryFn: () => apiFetch<Organization[]>("/organizations/")});
  const project = projects.find((item) => item.project_id === projectId);
  const nav = navigation(projectId);
  const breadcrumbs = pathname.split("/").filter(Boolean).map((segment) => routeLabel(segment, project));
  const searchResults = useMemo(() => {
    const value = search.trim().toLowerCase();
    if (!value) return projects.slice(0, 5);
    return projects.filter((item) => item.name.toLowerCase().includes(value)).slice(0, 8);
  }, [projects, search]);
  const isWorkspaceRoute = /^\/projects\/[^/]+\/(sources|playground|documents)$/.test(pathname);

  const switchOrganization = useMutation({
    mutationFn: (organizationId: string) => apiFetch<User>("/auth/me", {method: "PATCH", body: JSON.stringify({organization_id: organizationId})}),
    onSuccess: async () => {
      await queryClient.invalidateQueries({queryKey: ["me"]});
      toast.success("Organization context updated");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Unable to switch organization"),
  });

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen(true);
      }
      if (event.key === "Escape") {
        setPaletteOpen(false);
        setNotificationsOpen(false);
        setUserMenuOpen(false);
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  useEffect(() => {
    if (!paletteOpen) return;
    const timer = window.setTimeout(() => searchRef.current?.focus(), 20);
    return () => window.clearTimeout(timer);
  }, [paletteOpen]);

  function toggleCollapsed() {
    setCollapsed((value) => {
      localStorage.setItem("ragforge:sidebar-collapsed", String(!value));
      return !value;
    });
  }

  async function logout() {
    await authFetch("/logout");
    router.replace("/login");
    router.refresh();
  }

  function active(item: NavItem) {
    if (item.label === "Projects") return pathname === "/projects";
    if (item.href.endsWith("/playground") && pathname.includes("/history")) return true;
    if (item.href.endsWith("/pipelines") && pathname.includes("/runs")) return true;
    if (item.href.endsWith("/sources") && pathname.includes("/documents")) return true;
    return pathname === item.href || pathname.startsWith(`${item.href}/`);
  }

  const sidebar = (mobile = false) => (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center gap-3 border-b border-white/[0.08] px-3">
        <Link href="/projects" className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-[var(--ink-inverse)]" aria-label="RAGForge home">
          <Sparkles className="size-5" />
        </Link>
        {(!collapsed || mobile) ? <span className="min-w-0 flex-1 truncate text-sm font-semibold tracking-tight">RAGForge</span> : null}
        {mobile ? <button className="icon-button" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X className="size-4" /></button> : null}
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-3" aria-label="Primary navigation">
        {projectId && project ? <div className={cn("mb-3 rounded-xl border border-white/[0.08] bg-white/[0.025] p-3", collapsed && !mobile && "hidden")}>
          <Link href="/projects" onClick={() => setMobileOpen(false)} className="text-[9px] text-[#817a72] hover:text-white">Back to all projects</Link>
          <p className="mt-2 truncate text-xs font-semibold text-[var(--ink)]">{project.name}</p>
          <p className="mono mt-1 truncate text-[8px] text-[#5c5751]">{project.project_id}</p>
        </div> : null}
        <div className="space-y-4">
          {nav.map((group) => <div key={group.label}>
            {(!collapsed || mobile) ? <p className="mb-1.5 px-3 text-[8px] font-semibold uppercase tracking-[.16em] text-[#5c5751]">{group.label}</p> : null}
            <div className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                const selected = active(item);
                return <Link
                  key={`${group.label}:${item.label}`}
                  href={item.href}
                  title={collapsed && !mobile ? item.label : undefined}
                  aria-current={selected ? "page" : undefined}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "group flex h-10 items-center gap-3 rounded-[10px] border px-3 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]",
                    selected ? "border-[var(--accent-border)] bg-[var(--surface-active)] text-[var(--accent-strong)] shadow-[var(--shadow-accent)]" : "border-transparent text-[#aaa39a] hover:bg-[var(--surface-hover)] hover:text-white",
                    collapsed && !mobile && "justify-center px-0",
                  )}
                >
                  <Icon className="size-[17px] shrink-0" strokeWidth={1.8} />
                  {(!collapsed || mobile) ? <span>{item.label}</span> : <span className="sr-only">{item.label}</span>}
                </Link>;
              })}
            </div>
          </div>)}
        </div>
      </nav>
      <div className="border-t border-white/[0.08] p-2">
        <button onClick={toggleCollapsed} className={cn("hidden h-10 w-full items-center gap-3 rounded-[10px] px-3 text-[11px] text-[#8f877f] hover:bg-white/[0.04] hover:text-white md:flex", collapsed && "justify-center px-0")} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          {collapsed ? <PanelLeftOpen className="size-4" /> : <><PanelLeftClose className="size-4" /><span>Collapse sidebar</span></>}
        </button>
      </div>
    </div>
  );

  return <div className="min-h-dvh bg-[var(--background)] text-[var(--ink)]">
    <aside className={cn("fixed inset-y-0 left-0 z-50 hidden border-r border-[var(--border)] bg-[#090909] transition-[width] duration-200 md:block", collapsed ? "w-[68px]" : "w-[214px]")}>{sidebar()}</aside>

    <div className={cn("min-h-dvh transition-[padding] duration-200", collapsed ? "md:pl-[68px]" : "md:pl-[214px]")}>
      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-[var(--border)] bg-[#090909]/95 px-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-2">
          <button className="icon-button md:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu className="size-5" /></button>
          <nav className="hidden min-w-0 items-center gap-1.5 sm:flex" aria-label="Breadcrumbs">
            <Link href="/projects" className="text-[11px] text-[#8f877f] hover:text-white">RAGForge</Link>
            {breadcrumbs.slice(-3).map((label, index, shown) => <span key={`${label}-${index}`} className="flex min-w-0 items-center gap-1.5">
              <ChevronRight className="size-3 shrink-0 text-[#403c36]" />
              <span className={cn("max-w-40 truncate text-[11px] capitalize", index === shown.length - 1 ? "text-[#f4efe7]" : "text-[#8f877f]")}>{label}</span>
            </span>)}
          </nav>
          <span className="truncate text-sm font-medium sm:hidden">{breadcrumbs.at(-1) ?? "RAGForge"}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <label className="hidden h-9 items-center gap-2 rounded-[10px] border border-white/[0.08] bg-white/[0.025] px-2.5 lg:flex">
            <Building2 className="size-3.5 text-[#77716a]" />
            <span className="sr-only">Organization</span>
            <select
              value={user?.organization_id ?? ""}
              onChange={(event) => switchOrganization.mutate(event.target.value)}
              className="max-w-40 bg-transparent text-[11px] text-[#c9c1b7] outline-none"
              aria-label="Organization switcher"
            >
              <option value="">Personal workspace</option>
              {organizations.map((organization) => <option key={organization.organization_id} value={organization.organization_id}>{organization.name}</option>)}
            </select>
            <ChevronDown className="size-3 text-[#5f5952]" />
          </label>
          {projectId ? <label className="hidden h-9 items-center gap-2 rounded-[10px] border border-white/[0.08] bg-white/[0.025] px-2.5 xl:flex">
            <FolderKanban className="size-3.5 text-[#817a72]" />
            <span className="sr-only">Project</span>
            <select
              value={projectId}
              onChange={(event) => router.push(`/projects/${event.target.value}/overview`)}
              className="max-w-44 bg-transparent text-[11px] text-[#d8d2ca] outline-none"
              aria-label="Project switcher"
            >
              {projects.map((item) => <option key={item.project_id} value={item.project_id}>{item.name}</option>)}
            </select>
            <ChevronDown className="size-3 text-[#5c5751]" />
          </label> : null}
          <button onClick={() => setPaletteOpen(true)} className="hidden h-9 w-52 items-center gap-2 rounded-[10px] border border-white/[0.08] bg-white/[0.025] px-3 text-left text-[10px] text-[#77716a] hover:border-white/[0.15] lg:flex" aria-label="Open global search">
            <Search className="size-3.5" /><span className="flex-1">Search projects</span><kbd className="rounded border border-white/10 px-1.5 py-0.5 text-[8px]">⌘ K</kbd>
          </button>
          <button className="icon-button lg:hidden" onClick={() => setPaletteOpen(true)} aria-label="Open global search"><Search className="size-4" /></button>
          <div className="relative">
            <button className="icon-button" onClick={() => {setNotificationsOpen((value) => !value); setUserMenuOpen(false);}} aria-label="Notifications" aria-expanded={notificationsOpen}><Bell className="size-4" /></button>
            {notificationsOpen ? <div className="popover right-0 top-11 w-72 p-4"><p className="text-xs font-semibold">Notifications</p><div className="mt-4 rounded-lg bg-white/[0.025] p-4 text-center"><Bell className="mx-auto size-4 text-[#5f5952]" /><p className="mt-2 text-[10px] text-[#aaa39a]">No new notifications</p><p className="mt-1 text-[8px] text-[#5f5952]">Pipeline failures remain visible in ingestion runs.</p></div></div> : null}
          </div>
          <div className="relative">
            <button onClick={() => {setUserMenuOpen((value) => !value); setNotificationsOpen(false);}} className="flex h-9 items-center gap-2 rounded-[10px] px-1.5 hover:bg-white/[0.04]" aria-label="User menu" aria-expanded={userMenuOpen}>
              <span className="flex size-7 items-center justify-center rounded-full bg-[var(--surface-raised)] text-[9px] font-semibold text-[var(--accent-strong)]">{user ? initials(user.full_name, user.email) : "…"}</span>
              <ChevronDown className="hidden size-3 text-[#77716a] sm:block" />
            </button>
            {userMenuOpen ? <div className="popover right-0 top-11 w-56 p-1.5">
              <div className="border-b border-white/[0.08] px-2.5 py-2"><p className="truncate text-[11px] font-medium">{user?.full_name || "RAGForge user"}</p><p className="mt-0.5 truncate text-[9px] text-[#77716a]">{user?.email}</p></div>
              <Link href="/settings/profile" onClick={() => setUserMenuOpen(false)} className="menu-item"><UserRound className="size-3.5" />Profile settings</Link>
              <button onClick={logout} className="menu-item w-full"><LogOut className="size-3.5" />Sign out</button>
            </div> : null}
          </div>
        </div>
      </header>
      <main className={cn("min-h-[calc(100dvh-4rem)]", isWorkspaceRoute ? "h-[calc(100dvh-4rem)] overflow-hidden" : "px-4 py-6 sm:px-6 lg:px-8 lg:py-8")}>{children}</main>
    </div>

    {mobileOpen ? <div className="fixed inset-0 z-[100] md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
      <button className="absolute inset-0 bg-black/65" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />
      <aside className="relative h-full w-[min(19rem,88vw)] border-r border-[var(--border)] bg-[#090909] shadow-2xl">{sidebar(true)}</aside>
    </div> : null}

    {paletteOpen ? <div className="fixed inset-0 z-[110] flex items-start justify-center bg-black/70 px-4 pt-[12vh]" role="dialog" aria-modal="true" aria-label="Global search" onMouseDown={(event) => {if (event.target === event.currentTarget) setPaletteOpen(false);}}>
      <div className="w-full max-w-xl overflow-hidden rounded-xl border border-white/10 bg-[var(--surface-muted)] shadow-2xl">
        <label className="flex h-13 items-center gap-3 border-b border-white/[0.08] px-4"><Search className="size-4 text-[#77716a]" /><span className="sr-only">Search projects</span><input ref={searchRef} value={search} onChange={(event) => setSearch(event.target.value)} className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#5f5952]" placeholder="Search projects…" /><button onClick={() => setPaletteOpen(false)} className="rounded border border-white/10 px-1.5 py-1 text-[8px] text-[#77716a]">ESC</button></label>
        <div className="max-h-80 overflow-y-auto p-2">
          <p className="px-2 py-1.5 text-[8px] font-semibold uppercase tracking-[.14em] text-[#5f5952]">Projects</p>
          {searchResults.map((item) => <button key={item.project_id} onClick={() => {router.push(`/projects/${item.project_id}/overview`); setPaletteOpen(false);}} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-white/[0.04]"><span className="flex size-8 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]"><FolderKanban className="size-4" /></span><span className="min-w-0 flex-1"><span className="block truncate text-[11px] font-medium">{item.name}</span><span className="font-mono text-[8px] text-[#5f5952]">{item.project_id}</span></span><ChevronRight className="size-3 text-[#5f5952]" /></button>)}
          {!searchResults.length ? <p className="px-3 py-8 text-center text-[10px] text-[#77716a]">No projects match “{search}”.</p> : null}
        </div>
        <div className="flex items-center gap-4 border-t border-white/[0.08] px-4 py-2 text-[8px] text-[#5f5952]"><span><kbd>↑↓</kbd> navigate</span><span><kbd>↵</kbd> open</span><span className="ml-auto flex items-center gap-1"><Command className="size-2.5" />K anywhere</span></div>
      </div>
    </div> : null}
  </div>;
}
