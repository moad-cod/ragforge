import type {Metadata} from "next";
import {GeistSans} from "geist/font/sans";
import {GeistMono} from "geist/font/mono";
import {Providers} from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAGForge",
  description: "Build, inspect, and query durable RAG knowledge bases.",
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
