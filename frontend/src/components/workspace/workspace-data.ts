import type {Document as ApiDocument} from "@/lib/types";

export type WorkspaceDocument = ApiDocument & {
  size: string;
  pages: number;
  chunks: number;
  version: number;
  owner: string;
  progress?: number;
  stage?: "Bronze" | "Silver" | "Gold" | "Qdrant";
  statusText?: string;
  error?: string;
};

export const chunkers = [
  {id: "fixed_size", name: "Starter Chunking", tier: "Foundation", status: "Stable", detail: "Fast, sensible defaults"},
  {id: "paragraph", name: "Base Chunking", tier: "Foundation", status: "Stable", detail: "Paragraph-aware splitting"},
  {id: "sentence", name: "Precision Chunking", tier: "Advanced", status: "Stable", detail: "High recall and clean boundaries"},
  {id: "semantic", name: "Semantic Chunking", tier: "Advanced", status: "Beta", detail: "Meaning-aware segmentation"},
  {id: "hierarchical", name: "Structured Chunking", tier: "Specialized", status: "Stable", detail: "Tables and hierarchical content"},
  {id: "late_chunking", name: "Late Interaction Chunking", tier: "Expert", status: "Beta", detail: "Fine-grained token retrieval"},
  {id: "proposition", name: "Ultimate Chunking", tier: "Expert", status: "Experimental", detail: "Multi-pass enriched chunks"},
  {id: "multimodal", name: "Multimodal Chunking", tier: "Specialized", status: "Experimental", detail: "Text, figures and images"},
];
