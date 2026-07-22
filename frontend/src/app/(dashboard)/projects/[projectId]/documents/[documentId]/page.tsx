import {DocumentDetail} from "@/components/document-detail";
export default async function DocumentPage({params}: {params: Promise<{projectId: string; documentId: string}>}) {const {projectId, documentId} = await params; return <DocumentDetail projectId={projectId} documentId={documentId} />;}
