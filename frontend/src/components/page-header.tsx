export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow ? (
          <p className="mb-1 text-xs font-bold uppercase tracking-[0.12em] text-[var(--accent)]">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-[28px] font-semibold leading-[1.2] tracking-[-0.02em] text-[var(--ink)]">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-sm leading-[1.6] text-[var(--ink-muted)]">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex w-full items-center gap-2 sm:w-auto">{actions}</div> : null}
    </header>
  );
}
