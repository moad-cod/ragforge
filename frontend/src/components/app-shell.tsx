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
  return pathname.match(/^\/projects\/([^/]+)/)?.[1] ?? null;
}

const nav = [
  {label: "Workspace", icon: Blocks},
  {label: "Projects", icon: FolderKanban, href: "/projects"},
  {label: "Query history", icon: Clock3},
  {label: "Pipeline runs", icon: Network},
  {label: "Analytics", icon: BarChart3},
  {label: "Settings", icon: Settings},
];

function RailButton({label, active, icon: Icon, onClick}: {
  label: string;
  active?: boolean;
  icon: typeof Blocks;
  onClick?: () => void;
}) {
  return (
    <button
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        "group relative flex size-10 items-center justify-center rounded-[10px] text-[#71847b] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400",
        active ? "bg-emerald-400/12 text-[#2bdf95]" : "hover:bg-white/[0.05] hover:text-[#c4d1cb]",
      )}
    >
      <Icon className="size-[18px]" strokeWidth={1.8} />
      <span className="pointer-events-none absolute left-[calc(100%+10px)] z-[80] hidden whitespace-nowrap rounded-md border border-white/10 bg-[#13251e] px-2 py-1.5 text-[11px] font-medium text-white shadow-xl group-hover:block">
        {label}
      </span>
    </button>
  );
}

export function AppShell({children}: {children: React.ReactNode}) {
  const pathname = usePathname();
  const router = useRouter();
  const projectId = projectIdFromPath(pathname);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const {data: user} = useQuery({queryKey: ["me"], queryFn: () => apiFetch<User>("/auth/me")});
  const {data: projects = []} = useQuery({queryKey: ["projects"], queryFn: () => apiFetch<Project[]>("/projects/")});
  const project = useMemo(() => projects.find((item) => item.project_id === projectId), [projectId, projects]);
  const isWorkspace = Boolean(projectId);

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
      if (event.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  async function logout() {
    await authFetch("/logout");
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="h-dvh overflow-hidden bg-[#07110d] text-[#f1f5f3]">
      <aside className="fixed inset-y-0 left-0 z-50 hidden w-[60px] flex-col items-center border-r border-white/[0.08] bg-[#08130f] py-3 md:flex">
        <Link href="/projects" title="RAGForge" className="group mb-4 flex size-10 items-center justify-center rounded-xl bg-emerald-400 text-[#052116] shadow-[inset_0_0_0_1px_rgba(255,255,255,.18)]">
          <Sparkles className="size-[19px]" strokeWidth={2.2} />
        </Link>
        <div className="flex flex-col gap-1.5">
          {nav.map((item, index) => item.href ? (
            <Link key={item.label} href={item.href} aria-label={item.label} title={item.label} className="group relative">
              <span className={cn("flex size-10 items-center justify-center rounded-[10px] text-[#71847b] transition hover:bg-white/[0.05] hover:text-[#c4d1cb]", !projectId && index === 1 && "bg-emerald-400/12 text-[#2bdf95]") }>
                <item.icon className="size-[18px]" strokeWidth={1.8} />
              </span>
            </Link>
          ) : <RailButton key={item.label} {...item} active={Boolean(projectId) && index === 0} />)}
        </div>
        <div className="mt-auto flex flex-col items-center gap-1.5">
          <RailButton label="Help center" icon={CircleHelp} />
          <RailButton label="Dark theme" icon={Moon} />
          <button aria-label="Sign out" title="Sign out" onClick={logout} className="relative mt-2 flex size-9 items-center justify-center rounded-full bg-[#26483b] text-[11px] font-semibold text-emerald-100 ring-2 ring-[#07110d] transition hover:ring-emerald-400/40">
            {user ? initials(user.full_name, user.email) : "AH"}
            <span className="absolute bottom-0 right-0 size-2.5 rounded-full border-2 border-[#08130f] bg-emerald-400" />
          </button>
        </div>
      </aside>

      <div className="flex h-full flex-col md:pl-[60px]">
        <header className="z-40 flex h-[54px] shrink-0 items-center justify-between border-b border-white/[0.08] bg-[#09140f] px-3 md:px-4">
          <div className="flex min-w-0 items-center gap-2">
            <button onClick={() => setMobileOpen(true)} className="flex size-8 items-center justify-center rounded-lg text-[#93a39c] hover:bg-white/5 md:hidden" aria-label="Open navigation"><Menu className="size-5" /></button>
            <div className="hidden items-center gap-2 text-[12px] sm:flex">
              <span className="text-[#64736d]">Organization</span><span className="text-[#40524a]">/</span>
              <span className="max-w-40 truncate text-[#a9b7b0]">{project?.name ?? (isWorkspace ? "Research workspace" : "Projects")}</span>
              {isWorkspace ? <><span className="text-[#40524a]">/</span><span className="text-[#f1f5f3]">Workspace</span></> : null}
            </div>
            {isWorkspace ? <span className="ml-1 hidden items-center gap-1.5 rounded-full border border-emerald-400/20 bg-emerald-400/[0.07] px-2 py-1 text-[10px] font-medium text-emerald-300 lg:flex"><span className="size-1.5 rounded-full bg-emerald-400" />Ready</span> : null}
          </div>
          <div className="flex items-center gap-1.5">
            <button onClick={() => setSearchOpen(true)} className="hidden h-8 w-48 items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.025] px-2.5 text-left text-[11px] text-[#64736d] hover:border-white/[0.14] lg:flex">
              <Search className="size-3.5" /><span className="flex-1">Search workspace</span><span className="flex items-center gap-0.5 rounded border border-white/10 px-1 py-0.5 text-[9px]"><Command className="size-2.5" />K</span>
            </button>
            <button aria-label="Notifications" className="relative flex size-8 items-center justify-center rounded-lg text-[#7f9188] hover:bg-white/5 hover:text-white"><Bell className="size-4" /><span className="absolute right-2 top-1.5 size-1.5 rounded-full bg-emerald-400" /></button>
            <button className="hidden h-8 items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.025] px-2.5 text-[11px] text-[#cbd5d0] sm:flex">
              <span className="flex size-4 items-center justify-center rounded bg-[#4285f4] text-[9px] font-bold text-white">G</span>Gemini 2.5 Flash<ChevronDown className="size-3 text-[#64736d]" />
            </button>
            <button aria-label="User menu" className="ml-1 flex size-8 items-center justify-center rounded-full bg-[#26483b] text-[10px] font-semibold text-emerald-100">{user ? initials(user.full_name, user.email) : "AH"}</button>
          </div>
        </header>

        <main className={cn("min-h-0 flex-1 pb-12 md:pb-0", isWorkspace ? "overflow-hidden" : "overflow-y-auto px-5 py-7 sm:px-8 sm:py-9")}>{children}</main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-[70] flex h-12 items-center justify-around border-t border-white/[0.09] bg-[#09140f]/95 px-3 backdrop-blur md:hidden" aria-label="Mobile navigation">
        {[{label:"Workspace",icon:Blocks},{label:"Documents",icon:FileStack},{label:"History",icon:Clock3},{label:"Runs",icon:Network}].map(({label,icon:Icon}, index) => <button key={label} className={cn("flex min-w-14 flex-col items-center gap-0.5 text-[8px]", index === 0 ? "text-emerald-300" : "text-[#64736d]")}><Icon className="size-3.5" />{label}</button>)}
      </nav>

      {mobileOpen ? <div className="fixed inset-0 z-[90] md:hidden">
        <button aria-label="Close menu" className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
        <aside className="relative h-full w-64 border-r border-white/10 bg-[#09140f] p-4">
          <div className="mb-7 flex items-center justify-between"><span className="flex items-center gap-2 text-sm font-semibold"><span className="flex size-8 items-center justify-center rounded-lg bg-emerald-400 text-[#052116]"><Sparkles className="size-4" /></span>RAGForge</span><button onClick={() => setMobileOpen(false)}><X className="size-4" /></button></div>
          <nav className="space-y-1">{nav.map((item) => <button key={item.label} onClick={() => { if (item.href) router.push(item.href); setMobileOpen(false); }} className="flex h-10 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-[#93a39c] hover:bg-white/5 hover:text-white"><item.icon className="size-4" />{item.label}</button>)}</nav>
          <button onClick={logout} className="absolute bottom-5 left-4 flex items-center gap-2 text-sm text-[#93a39c]"><LogOut className="size-4" />Sign out</button>
        </aside>
      </div> : null}

      {searchOpen ? <div className="fixed inset-0 z-[100] flex items-start justify-center bg-black/60 px-4 pt-[14vh] backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) setSearchOpen(false); }}>
        <div className="w-full max-w-xl overflow-hidden rounded-xl border border-white/10 bg-[#0e1c17] shadow-2xl">
          <div className="flex items-center gap-3 border-b border-white/10 px-4"><Search className="size-4 text-[#64736d]" /><input autoFocus className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-[#64736d]" placeholder="Search projects, documents, queries…" /><span className="rounded border border-white/10 px-1.5 py-0.5 text-[10px] text-[#64736d]">ESC</span></div>
          <div className="p-5 text-center"><Search className="mx-auto size-4 text-[#53625b]" /><p className="mt-2 text-[10px] text-[#93a39c]">Start typing to search your workspace</p><p className="mt-1 text-[8px] text-[#53625b]">Results will come from your projects, documents, and query history.</p></div>
        </div>
      </div> : null}
    </div>
  );
}
