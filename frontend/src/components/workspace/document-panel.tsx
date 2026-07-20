"use client";

import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronUp,
  Cloud,
  File,
  FileSpreadsheet,
  FileText,
  FolderInput,
  Link2,
  ListFilter,
  MoreHorizontal,
  RefreshCw,
  Search,
  Settings2,
  SlidersHorizontal,
  UploadCloud,
  X,
} from "lucide-react";
import {useMemo, useRef, useState} from "react";
import {cn} from "@/lib/utils";
import {chunkers, type WorkspaceDocument} from "@/components/workspace/workspace-data";

const statusStyle: Record<string, string> = {
  indexed: "bg-emerald-400/10 text-emerald-300",
  running: "bg-blue-400/10 text-blue-300",
  queued: "bg-amber-400/10 text-amber-300",
  failed: "bg-red-400/10 text-red-300",
  landed: "bg-white/5 text-[#93a39c]",
};

function FileIcon({extension}: {extension: string | null}) {
  const Icon = extension === ".xlsx" || extension === ".csv" ? FileSpreadsheet : extension === ".docx" ? FileText : File;
  const tone = extension === ".pdf" ? "text-red-300 bg-red-400/10" : extension === ".xlsx" ? "text-emerald-300 bg-emerald-400/10" : "text-blue-300 bg-blue-400/10";
  return <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", tone)}><Icon className="size-4" /></span>;
}

function Pipeline({document}: {document: WorkspaceDocument}) {
  const steps = ["Bronze", "Silver", "Gold", "Qdrant"];
  const active = Math.max(0, steps.indexOf(document.stage ?? "Bronze"));
  return <div className="mt-3 rounded-lg border border-blue-400/10 bg-blue-400/[0.035] p-2.5">
    <div className="mb-2 flex items-center justify-between"><span className="text-[10px] text-blue-200">{document.statusText ?? "Processing document"}</span>{document.progress !== undefined ? <span className="font-mono text-[10px] text-blue-300">{document.progress}%</span> : null}</div>
    <div className="flex items-center">{steps.map((step, index) => <div key={step} className="flex flex-1 items-center last:flex-none">
      <span className={cn("flex size-4 items-center justify-center rounded-full border text-[8px]", index < active ? "border-emerald-400 bg-emerald-400 text-[#07110d]" : index === active ? "border-blue-400 bg-blue-400/20 text-blue-200" : "border-white/15 text-[#64736d]")}>{index < active ? <Check className="size-2.5" /> : index + 1}</span>
      {index < steps.length - 1 ? <span className={cn("mx-1 h-px flex-1", index < active ? "bg-emerald-400/60" : "bg-white/10")} /> : null}
    </div>)}</div>
    <div className="mt-1.5 flex justify-between text-[8px] text-[#64736d]">{steps.map((step) => <span key={step}>{step}</span>)}</div>
  </div>;
}

function DocumentCard({document, selected, onSelect}: {document: WorkspaceDocument; selected: boolean; onSelect: () => void}) {
  const [menu, setMenu] = useState(false);
  return <article onClick={onSelect} className={cn("relative border-b border-white/[0.07] px-3 py-3 transition", selected ? "bg-emerald-400/[0.065] before:absolute before:inset-y-0 before:left-0 before:w-0.5 before:bg-emerald-400" : "hover:bg-white/[0.025]")}>
    <div className="flex items-start gap-2.5">
      <FileIcon extension={document.extension} />
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <button className="min-w-0 truncate text-left text-[12px] font-medium text-[#e5ece8]">{document.filename}</button>
          <button aria-label={`More actions for ${document.filename}`} onClick={(event) => {event.stopPropagation(); setMenu((value) => !value);}} className="flex size-6 shrink-0 items-center justify-center rounded text-[#64736d] hover:bg-white/5 hover:text-white"><MoreHorizontal className="size-3.5" /></button>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[9px] text-[#64736d]">
          {document.size ? <span>{document.size}</span> : null}{document.pages > 0 ? <><span>·</span><span>{document.pages} pages</span></> : null}{document.version > 0 ? <><span>·</span><span>v{document.version}</span></> : null}
          <span className={cn("ml-auto rounded-full px-1.5 py-0.5 font-medium capitalize", statusStyle[document.status] ?? statusStyle.landed)}>{document.status}</span>
        </div>
        {document.status === "indexed" ? <div className="mt-1.5 flex items-center justify-between text-[9px] text-[#64736d]"><span>{document.chunks > 0 ? `${document.chunks} chunks · ` : ""}Indexed</span>{document.owner ? <span className="flex size-4 items-center justify-center rounded-full bg-[#29463b] text-[7px] text-emerald-100">{document.owner}</span> : null}</div> : null}
        {(document.status === "running" || document.status === "queued") && document.progress !== undefined ? <Pipeline document={document} /> : null}
        {document.status === "failed" ? <div className="mt-2 rounded-lg border border-red-400/10 bg-red-400/[0.04] p-2"><p className="line-clamp-2 text-[9px] leading-4 text-red-200/80">{document.error}</p><div className="mt-1.5 flex gap-2"><button className="flex items-center gap-1 text-[9px] font-medium text-red-300"><RefreshCw className="size-2.5" />Retry</button><button className="text-[9px] text-[#93a39c] hover:text-white">Technical details</button></div></div> : null}
      </div>
    </div>
    {menu ? <div className="absolute right-3 top-9 z-30 w-40 rounded-lg border border-white/10 bg-[#13251e] p-1 shadow-xl" onClick={(event) => event.stopPropagation()}>{["Open", "Rename", "View versions", "Retry ingestion", "Copy document ID", "Delete"].map((label) => <button key={label} className={cn("block w-full rounded px-2.5 py-1.5 text-left text-[10px] hover:bg-white/5", label === "Delete" ? "text-red-300" : "text-[#cbd5d0]")}>{label}</button>)}</div> : null}
  </article>;
}

export function DocumentPanel({projectName, documents, selectedIds, selectedDocumentId, onSelectDocument, onToggleSelected, onUpload}: {
  projectName: string;
  documents: WorkspaceDocument[];
  selectedIds: string[];
  selectedDocumentId: string;
  onSelectDocument: (id: string) => void;
  onToggleSelected: (id: string) => void;
  onUpload: (file: File, chunker: string) => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All");
  const [uploadOpen, setUploadOpen] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [chunker, setChunker] = useState("paragraph");
  const [chunkerOpen, setChunkerOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const filtered = useMemo(() => documents.filter((doc) => (filter === "All" || doc.status === filter.toLowerCase()) && (doc.filename ?? "").toLowerCase().includes(search.toLowerCase())), [documents, filter, search]);
  const indexed = documents.filter((doc) => doc.status === "indexed").length;
  const chunks = documents.reduce((total, doc) => total + doc.chunks, 0);

  async function submit() {
    if (!selectedFile) return;
    setUploading(true);
    try { await onUpload(selectedFile, chunker); setSelectedFile(null); } finally { setUploading(false); }
  }

  return <section className="flex h-full min-w-0 flex-col bg-[#0a1511]">
    <div className="flex h-[49px] shrink-0 items-center justify-between border-b border-white/[0.08] px-3">
      <div className="min-w-0"><button className="flex items-center gap-1 text-[9px] text-[#64736d] hover:text-[#93a39c]"><ArrowLeft className="size-2.5" />All projects</button><div className="mt-0.5 flex items-center gap-2"><h1 className="truncate text-[13px] font-semibold">{projectName}</h1></div></div>
      <button aria-label="Project settings" className="flex size-7 items-center justify-center rounded-lg text-[#64736d] hover:bg-white/5 hover:text-white"><Settings2 className="size-3.5" /></button>
    </div>

    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="border-b border-white/[0.08] p-3">
        <button onClick={() => setUploadOpen((value) => !value)} className="flex w-full items-center justify-between text-[11px] font-semibold"><span className="flex items-center gap-2"><UploadCloud className="size-3.5 text-emerald-400" />Add knowledge</span>{uploadOpen ? <ChevronUp className="size-3.5 text-[#64736d]" /> : <ChevronDown className="size-3.5 text-[#64736d]" />}</button>
        {uploadOpen ? <div className="mt-2.5">
          <button onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDragEnter={() => setDragging(true)} onDragLeave={() => setDragging(false)} onDrop={(event) => {event.preventDefault(); setDragging(false); setSelectedFile(event.dataTransfer.files[0] ?? null);}} className={cn("flex min-h-[76px] w-full flex-col items-center justify-center rounded-lg border border-dashed px-3 text-center transition", dragging ? "border-emerald-400 bg-emerald-400/5" : "border-white/[0.14] bg-white/[0.018] hover:border-emerald-400/40")}>
            <UploadCloud className="mb-1.5 size-4 text-emerald-400" /><span className="text-[10px] font-medium text-[#cbd5d0]">{selectedFile ? selectedFile.name : "Drop files here or browse"}</span><span className="mt-0.5 text-[8px] text-[#64736d]">PDF, DOCX, PPTX, XLSX, CSV, TXT, HTML · 25 MB max</span>
          </button>
          <input ref={inputRef} type="file" className="hidden" accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,.html" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
          <div className="mt-2 flex gap-1.5"><button className="flex flex-1 items-center justify-center gap-1 rounded-md border border-white/[0.08] py-1.5 text-[9px] text-[#93a39c] hover:bg-white/5"><Link2 className="size-2.5" />URL</button><button className="flex flex-1 items-center justify-center gap-1 rounded-md border border-white/[0.08] py-1.5 text-[9px] text-[#93a39c] hover:bg-white/5"><Cloud className="size-2.5" />Google Drive</button></div>
          <div className="relative mt-2">
            <button onClick={() => setChunkerOpen((value) => !value)} className="flex h-8 w-full items-center justify-between rounded-lg border border-white/[0.09] bg-white/[0.025] px-2.5 text-left"><span><span className="block text-[8px] text-[#64736d]">Chunking strategy</span><span className="block text-[10px] text-[#dce6e1]">{chunkers.find((item) => item.id === chunker)?.name ?? chunker}</span></span><ChevronDown className="size-3 text-[#64736d]" /></button>
            {chunkerOpen ? <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-40 max-h-64 overflow-y-auto rounded-lg border border-white/10 bg-[#13251e] p-1 shadow-2xl">{chunkers.map((item) => <button key={item.id} onClick={() => {setChunker(item.id); setChunkerOpen(false);}} className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left hover:bg-white/5"><span className={cn("flex size-3.5 shrink-0 items-center justify-center rounded-full border", item.id === chunker ? "border-emerald-400 bg-emerald-400 text-[#07110d]" : "border-white/20")}>{item.id === chunker ? <Check className="size-2.5" /> : null}</span><span className="min-w-0 flex-1"><span className="flex items-center justify-between"><span className="text-[10px] font-medium">{item.name}</span><span className={cn("rounded px-1 py-0.5 text-[7px]", item.status === "Stable" ? "bg-emerald-400/10 text-emerald-300" : item.status === "Beta" ? "bg-blue-400/10 text-blue-300" : "bg-amber-400/10 text-amber-300")}>{item.status}</span></span><span className="text-[8px] text-[#64736d]">{item.tier} · {item.detail}</span></span></button>)}</div> : null}
          </div>
          <button className="mt-1.5 flex items-center gap-1 text-[9px] text-[#64736d]"><SlidersHorizontal className="size-2.5" />Advanced ingestion options<ChevronDown className="size-2.5" /></button>
          {selectedFile ? <div className="mt-2 flex gap-1.5"><button onClick={() => setSelectedFile(null)} className="flex h-8 flex-1 items-center justify-center gap-1 rounded-lg border border-white/10 text-[9px] text-[#93a39c]"><X className="size-2.5" />Cancel</button><button disabled={uploading} onClick={submit} className="h-8 flex-[2] rounded-lg bg-emerald-400 text-[9px] font-semibold text-[#052116] hover:bg-emerald-300 disabled:opacity-50">{uploading ? "Uploading…" : "Start ingestion"}</button></div> : null}
        </div> : null}
      </div>

      <div className="grid grid-cols-4 border-b border-white/[0.08] px-2 py-2.5 text-center"><div><b className="block text-[11px]">{documents.length}</b><span className="text-[8px] text-[#64736d]">Documents</span></div><div><b className="block text-[11px] text-emerald-300">{indexed}</b><span className="text-[8px] text-[#64736d]">Indexed</span></div><div><b className="block text-[11px]">{chunks}</b><span className="text-[8px] text-[#64736d]">Chunks</span></div><div><b className="block text-[11px] text-red-300">{documents.filter((d) => d.status === "failed").length}</b><span className="text-[8px] text-[#64736d]">Failed</span></div></div>

      <div className="sticky top-0 z-20 border-b border-white/[0.08] bg-[#0a1511]/95 p-2 backdrop-blur">
        <div className="flex gap-1.5"><label className="flex h-8 flex-1 items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.02] px-2"><Search className="size-3 text-[#64736d]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search documents" className="min-w-0 flex-1 bg-transparent text-[10px] outline-none placeholder:text-[#53625b]" /></label><button aria-label="Sort and filter" className="flex size-8 items-center justify-center rounded-lg border border-white/[0.08] text-[#64736d]"><ListFilter className="size-3" /></button></div>
        <div className="mt-1.5 flex gap-1 overflow-x-auto">{["All", "Indexed", "Running", "Failed"].map((item) => <button key={item} onClick={() => setFilter(item)} className={cn("rounded-md px-2 py-1 text-[8px]", filter === item ? "bg-emerald-400/10 text-emerald-300" : "text-[#64736d] hover:text-[#93a39c]")}>{item}</button>)}</div>
      </div>
      <div>{filtered.map((document) => <div key={document.document_id} className="relative"><button onClick={() => onToggleSelected(document.document_id)} aria-label={`Select ${document.filename} for querying`} className={cn("absolute left-1 top-1 z-10 flex size-3 items-center justify-center rounded border", selectedIds.includes(document.document_id) ? "border-emerald-400 bg-emerald-400 text-[#07110d]" : "border-white/15 bg-[#0a1511]")}>{selectedIds.includes(document.document_id) ? <Check className="size-2" /> : null}</button><DocumentCard document={document} selected={selectedDocumentId === document.document_id} onSelect={() => onSelectDocument(document.document_id)} /></div>)}</div>
      {!filtered.length ? <div className="flex flex-col items-center px-4 py-12 text-center"><FolderInput className="size-5 text-[#64736d]" /><p className="mt-2 text-[11px]">{documents.length ? "No matching documents" : "No documents yet"}</p><p className="mt-1 text-[9px] text-[#64736d]">{documents.length ? "Try another status or filename." : "Upload a file to start building this knowledge base."}</p></div> : null}
    </div>
  </section>;
}
