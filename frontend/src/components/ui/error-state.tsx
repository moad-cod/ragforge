import {AlertTriangle, RefreshCw} from "lucide-react";
import {Button} from "@/components/ui/button";

export function ErrorState({title = "Something went wrong", description, onRetry}: {title?: string; description: string; onRetry?: () => void}) {
  return <div role="alert" className="flex min-h-64 flex-col items-center justify-center rounded-xl border border-red-400/15 bg-red-400/[0.035] px-6 text-center">
    <span className="flex size-11 items-center justify-center rounded-xl bg-red-400/10 text-red-300"><AlertTriangle className="size-5" /></span>
    <h3 className="mt-4 text-sm font-semibold">{title}</h3>
    <p className="mt-2 max-w-md text-xs leading-5 text-[#8fa098]">{description}</p>
    {onRetry ? <Button className="mt-5" variant="secondary" size="sm" onClick={onRetry}><RefreshCw className="size-3.5" />Try again</Button> : null}
  </div>;
}
