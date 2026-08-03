import {
  DatabaseZap,
  FileText,
  MessagesSquare,
  Route,
  Search,
} from "lucide-react";

export default function AuthLayout({children}: {children: React.ReactNode}) {
  return (
    <main className="min-h-screen bg-[#070707] text-[#f5f1eb]">
      <div className="mx-auto grid min-h-screen w-full max-w-[1440px] gap-8 px-5 py-6 sm:px-8 md:px-12 lg:grid-cols-[minmax(0,1.38fr)_minmax(420px,1fr)] lg:px-16">
        <ProductIntroduction />
        <section className="flex min-h-[calc(100vh-3rem)] items-start justify-center py-2 sm:py-6 lg:min-h-0 lg:items-center lg:py-12">
          <div className="w-full max-w-[460px]">
            <div className="mb-5 lg:hidden">
              <ProductMark compact />
            </div>
            <div className="rounded-2xl border border-[#25221f] bg-[#0d0d0d] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.5)] sm:p-8 lg:p-11">
              {children}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function ProductIntroduction() {
  return (
    <section className="relative hidden overflow-hidden py-12 lg:flex lg:min-h-screen lg:flex-col">
      <div className="pointer-events-none absolute inset-y-16 left-0 right-8 opacity-70 [background-image:linear-gradient(rgba(235,224,209,0.018)_1px,transparent_1px),linear-gradient(90deg,rgba(235,224,209,0.018)_1px,transparent_1px)] [background-size:28px_28px] [mask-image:radial-gradient(circle_at_36%_34%,black,transparent_68%)]" />
      <div className="pointer-events-none absolute left-[12%] top-[28%] h-72 w-72 rounded-full bg-[#ebe0d1]/[0.045] blur-3xl" />

      <div className="relative z-10">
        <ProductMark />
      </div>

      <div className="relative z-10 my-auto max-w-[720px]">
        <p className="font-mono text-[12px] font-medium uppercase text-[#c7b9a6]">
          RAG Engineering Control Plane
        </p>
        <h1 className="mt-5 max-w-[700px] text-[clamp(40px,5vw,60px)] font-semibold leading-[1.05]">
          Build reliable RAG systems, not black-box demos.
        </h1>
        <p className="mt-6 max-w-[560px] text-[17px] leading-8 text-[#aaa39a]">
          Ingest documents, inspect retrieval, trace citations, and evaluate
          every stage from one workspace.
        </p>
        <RAGWorkflow />
      </div>

      <div className="relative z-10 mt-10 flex flex-wrap gap-3 font-mono text-[12px] uppercase text-[#aaa39a]">
        {[
          "Project-scoped retrieval",
          "Source-aware answers",
          "Traceable pipeline",
        ].map((item) => (
          <span
            key={item}
            className="rounded-full border border-[#2a2825] bg-[#111111] px-3 py-1.5"
          >
            {item}
          </span>
        ))}
      </div>
    </section>
  );
}

function ProductMark({compact = false}: {compact?: boolean}) {
  return (
    <div className="flex items-center gap-3">
      <span
        className={[
          "flex items-center justify-center rounded-xl border border-[#2a2825] bg-[#111111] text-[#ebe0d1]",
          compact ? "size-9" : "size-10",
        ].join(" ")}
      >
        <DatabaseZap className={compact ? "size-4" : "size-5"} />
      </span>
      <div>
        <div className={compact ? "text-lg font-semibold" : "text-xl font-semibold"}>
          RAGForge
        </div>
        <div className="font-mono text-[11px] uppercase text-[#777169]">
          Control plane
        </div>
      </div>
    </div>
  );
}

function RAGWorkflow() {
  const steps = [
    {
      number: "01",
      title: "Ingest",
      description: "Documents → extraction → chunks",
      icon: FileText,
    },
    {
      number: "02",
      title: "Retrieve",
      description: "Query → relevant sources → context",
      icon: Search,
    },
    {
      number: "03",
      title: "Observe",
      description: "Citations → latency → retrieval trace",
      icon: Route,
    },
  ];

  return (
    <div className="mt-12 max-w-[640px] rounded-2xl border border-[#2a2825] bg-[#111111]/80 p-4 shadow-[0_18px_60px_rgba(0,0,0,0.3)]">
      <div className="grid gap-3 xl:grid-cols-3">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <div key={step.title} className="relative rounded-xl bg-[#181715] p-4">
              {index < steps.length - 1 ? (
                <span className="absolute left-[calc(100%+0.25rem)] top-1/2 hidden h-px w-2 bg-[#2a2825] xl:block" />
              ) : null}
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-[#777169]">{step.number}</span>
                <span className="flex size-8 items-center justify-center rounded-lg border border-[#2a2825] bg-[#111111] text-[#ebe0d1]">
                  <Icon className="size-4" />
                </span>
              </div>
              <h2 className="mt-4 text-sm font-semibold uppercase text-[#f5f1eb]">
                {step.title}
              </h2>
              <p className="mt-2 min-h-10 text-[13px] leading-5 text-[#aaa39a]">
                {step.description}
              </p>
            </div>
          );
        })}
      </div>
      <div className="mt-3 rounded-xl border border-[#2a2825] bg-[#0d0d0d] p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-[#f5f1eb]">
          <MessagesSquare className="size-4 text-[#ebe0d1]" />
          Document-to-answer workflow
        </div>
        <div className="mt-3 grid gap-2 font-mono text-[12px] text-[#aaa39a] sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <span>Documents → Chunking → Retrieval</span>
          <span className="hidden h-px w-8 bg-[#2a2825] sm:block" />
          <span>Grounded answer + trace</span>
        </div>
      </div>
    </div>
  );
}
