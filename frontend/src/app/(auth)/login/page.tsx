"use client";

import {zodResolver} from "@hookform/resolvers/zod";
import {ArrowRight, LoaderCircle} from "lucide-react";
import Link from "next/link";
import {useRouter} from "next/navigation";
import {useForm} from "react-hook-form";
import {toast} from "sonner";
import {z} from "zod";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {authFetch} from "@/lib/api";

const schema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: {errors, isSubmitting},
  } = useForm<Values>({resolver: zodResolver(schema)});

  const submit = handleSubmit(async (values) => {
    try {
      await authFetch("/login", values);
      router.replace("/projects");
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to sign in");
    }
  });

  return (
    <>
      <p className="text-sm font-semibold text-[var(--accent)]">Welcome back</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">
        Sign in to your workspace
      </h1>
      <p className="mt-3 text-sm leading-6 text-[var(--ink-muted)]">
        Continue managing your projects, documents, and grounded answers.
      </p>

      <form className="mt-8 space-y-5" onSubmit={submit}>
        <label className="block">
          <span className="mb-2 block text-sm font-medium">Email address</span>
          <Input
            autoComplete="email"
            placeholder="you@example.com"
            {...register("email")}
          />
          {errors.email ? (
            <span className="mt-1.5 block text-xs text-[var(--danger)]">
              {errors.email.message}
            </span>
          ) : null}
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-medium">Password</span>
          <Input
            type="password"
            autoComplete="current-password"
            placeholder="Your password"
            {...register("password")}
          />
          {errors.password ? (
            <span className="mt-1.5 block text-xs text-[var(--danger)]">
              {errors.password.message}
            </span>
          ) : null}
        </label>
        <Button className="w-full" size="lg" type="submit" disabled={isSubmitting}>
          {isSubmitting ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <ArrowRight className="size-4" />
          )}
          Sign in
        </Button>
      </form>

      <p className="mt-7 text-center text-sm text-[var(--ink-muted)]">
        New to RAGForge?{" "}
        <Link className="font-semibold text-[var(--accent)]" href="/register">
          Create an account
        </Link>
      </p>
    </>
  );
}
