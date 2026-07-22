"use client";

import {AlertTriangle, LoaderCircle, Trash2} from "lucide-react";
import {useState} from "react";
import {Button} from "@/components/ui/button";
import {Dialog} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";

export function ConfirmDeleteDialog({open, onClose, name, title, consequences, isPending, onConfirm}: {
  open: boolean;
  onClose: () => void;
  name: string;
  title: string;
  consequences: string;
  isPending?: boolean;
  onConfirm: () => void;
}) {
  const [confirmation, setConfirmation] = useState("");
  function close() {setConfirmation(""); onClose();}
  return <Dialog open={open} onClose={close} title={title} description="This action cannot be undone through RAGForge.">
    <div className="mt-5 rounded-lg border border-red-400/15 bg-red-400/[0.05] p-3 text-xs leading-5 text-red-200"><span className="flex items-center gap-2 font-semibold"><AlertTriangle className="size-4" />What will be removed</span><p className="mt-1.5 text-red-200/75">{consequences}</p></div>
    <label className="mt-5 block"><span className="mb-2 block text-xs font-medium">Type <strong className="text-white">{name}</strong> to confirm</span><Input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="off" /></label>
    <div className="mt-6 flex justify-end gap-2"><Button variant="secondary" onClick={close}>Cancel</Button><Button variant="danger" disabled={confirmation !== name || isPending} onClick={onConfirm}>{isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}Delete permanently</Button></div>
  </Dialog>;
}
