"use client";

import {useEffect, useRef, useState} from "react";
import {apiFetch} from "@/lib/api";
import {consumeSSE} from "@/lib/sse";
import type {IngestionRun, IngestionStatus, StreamEvent} from "@/lib/types";

const TERMINAL = new Set<IngestionStatus>(["indexed", "failed", "cancelled"]);

export function useIngestionStream(initial: IngestionRun) {
  const [run, setRun] = useState(initial);
  const [connected, setConnected] = useState(false);
  const statusRef = useRef(initial.status);

  useEffect(() => {
    if (TERMINAL.has(statusRef.current)) return;
    const controller = new AbortController();
    let mounted = true;
    const storageKey = `ragforge:ingestion:${initial.ingestion_run_id}:last-event-id`;

    const applyEvent = (event: StreamEvent) => {
      const status = event.status as IngestionStatus | undefined;
      if (!status) return;
      statusRef.current = status;
      setRun((current) => ({
        ...current,
        status,
        error_message:
          typeof event.error_message === "string"
            ? event.error_message
            : current.error_message,
        progress:
          event.progress && typeof event.progress === "object"
            ? (event.progress as IngestionRun["progress"])
            : current.progress,
        embedding_progress:
          event.embedding_progress && typeof event.embedding_progress === "object"
            ? (event.embedding_progress as IngestionRun["embedding_progress"])
            : current.embedding_progress,
      }));
    };

    async function recoverFromStatus() {
      const latest = await apiFetch<IngestionRun>(
        `/ingest/runs/${initial.ingestion_run_id}`,
      );
      if (!mounted) return;
      statusRef.current = latest.status;
      setRun(latest);
    }

    async function connect() {
      while (mounted && !TERMINAL.has(statusRef.current)) {
        try {
          const lastEventId = localStorage.getItem(storageKey);
          const headers = new Headers({Accept: "text/event-stream"});
          if (lastEventId) headers.set("Last-Event-ID", lastEventId);
          const response = await fetch(
            `/api/backend/ingest/runs/${initial.ingestion_run_id}/events`,
            {headers, signal: controller.signal, cache: "no-store"},
          );
          if (!mounted) return;
          setConnected(true);
          await consumeSSE(response, {
            onEvent: applyEvent,
            onId: (id) => localStorage.setItem(storageKey, id),
          });
        } catch {
          if (controller.signal.aborted) return;
          setConnected(false);
          try {
            await recoverFromStatus();
          } catch {
            // A later reconnect can recover from a transient API outage.
          }
        }
        if (!mounted || TERMINAL.has(statusRef.current)) return;
        await new Promise((resolve) => setTimeout(resolve, 1800));
      }
    }

    void connect();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [initial.ingestion_run_id]);

  return {run, connected};
}
