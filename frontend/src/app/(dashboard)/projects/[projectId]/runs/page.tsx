import {redirect} from "next/navigation";

export default async function ProjectRunsPage({params}: {params: Promise<{projectId: string}>}) {const {projectId} = await params; redirect(`/projects/${projectId}/pipelines?view=runs`);}
