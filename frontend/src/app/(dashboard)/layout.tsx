import {cookies} from "next/headers";
import {redirect} from "next/navigation";
import {AppShell} from "@/components/app-shell";
import {AUTH_COOKIE} from "@/lib/server-auth";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  if (!cookieStore.get(AUTH_COOKIE)?.value) redirect("/login");
  return <AppShell>{children}</AppShell>;
}
