import {ChatWorkspace} from "@/components/chat-workspace";

export default async function ChatPage({
  params,
}: {
  params: Promise<{projectId: string}>;
}) {
  const {projectId} = await params;
  return <ChatWorkspace projectId={projectId} />;
}
