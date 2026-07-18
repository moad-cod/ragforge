import {Brand} from "@/components/brand";

export default function AuthLayout({children}: {children: React.ReactNode}) {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
      <section className="subtle-grid hidden overflow-hidden bg-[var(--surface-dark)] p-12 text-white lg:flex lg:flex-col">
        <Brand inverse />
        <div className="my-auto max-w-xl">
          <div className="mb-6 inline-flex rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-indigo-200">
            Durable RAG operations, made visible
          </div>
          <h1 className="text-5xl font-semibold leading-[1.08] tracking-tight">
            Turn documents into an observable knowledge system.
          </h1>
          <p className="mt-6 max-w-lg text-lg leading-8 text-slate-300">
            Upload, track, query, and inspect every stage of your retrieval
            pipeline from one focused workspace.
          </p>
          <div className="mt-10 grid grid-cols-3 gap-4">
            {[
              ["Durable", "PostgreSQL truth"],
              ["Observable", "Live pipeline stages"],
              ["Grounded", "Traceable evidence"],
            ].map(([title, description]) => (
              <div
                key={title}
                className="rounded-2xl border border-white/10 bg-white/[0.04] p-4"
              >
                <div className="font-semibold">{title}</div>
                <div className="mt-1 text-xs text-slate-400">{description}</div>
              </div>
            ))}
          </div>
        </div>
        <p className="text-xs text-slate-500">
          RAGForge · Task 27 frontend control plane
        </p>
      </section>
      <section className="flex min-h-screen items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <Brand />
          </div>
          {children}
        </div>
      </section>
    </main>
  );
}
