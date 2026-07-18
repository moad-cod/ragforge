import type {Metadata} from "next";
import {Providers} from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAGForge",
  description: "Build, inspect, and query durable RAG knowledge bases.",
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
