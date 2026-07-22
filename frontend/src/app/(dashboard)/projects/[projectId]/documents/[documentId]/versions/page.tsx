import {DocumentDetail} from "@/components/document-detail";
export default async function VersionsPage({params}: {params: Promise<{projectId: string; documentId: string}>}) {const {projectId, documentId} = await params; return <DocumentDetail projectId={projectId} documentId={documentId} initialTab="versions" />;}
