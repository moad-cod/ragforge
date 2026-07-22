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

const schema = z
  .object({
    full_name: z.string().trim().min(2, "Enter your name"),
    email: z.email("Enter a valid email address"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string(),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords do not match",
  });
type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: {errors, isSubmitting},
  } = useForm<Values>({resolver: zodResolver(schema)});

  const submit = handleSubmit(async (formValues) => {
    const values = {
      full_name: formValues.full_name,
      email: formValues.email,
      password: formValues.password,
    };
    try {
      await authFetch("/register", values);
      await authFetch("/login", {email: values.email, password: values.password});
      router.replace("/projects");
      router.refresh();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Unable to create your account",
      );
    }
  });

  return (
    <>
      <p className="text-sm font-semibold text-[var(--accent)]">Get started</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">
        Create your RAGForge workspace
      </h1>
      <p className="mt-3 text-sm leading-6 text-[var(--ink-muted)]">
        No organization ID is needed. You can organize projects after sign-up.
      </p>

      <form className="mt-8 space-y-4" onSubmit={submit}>
        <label className="block">
          <span className="mb-2 block text-sm font-medium">Full name</span>
          <Input placeholder="Your name" {...register("full_name")} />
          {errors.full_name ? (
            <span className="mt-1.5 block text-xs text-[var(--danger)]">
              {errors.full_name.message}
            </span>
          ) : null}
        </label>
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
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-2 block text-sm font-medium">Password</span>
            <Input
              type="password"
              autoComplete="new-password"
              {...register("password")}
            />
            {errors.password ? (
              <span className="mt-1.5 block text-xs text-[var(--danger)]">
                {errors.password.message}
              </span>
            ) : null}
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-medium">Confirm</span>
            <Input
              type="password"
              autoComplete="new-password"
              {...register("confirmPassword")}
            />
            {errors.confirmPassword ? (
              <span className="mt-1.5 block text-xs text-[var(--danger)]">
                {errors.confirmPassword.message}
              </span>
            ) : null}
          </label>
        </div>
        <Button className="w-full" size="lg" type="submit" disabled={isSubmitting}>
          {isSubmitting ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <ArrowRight className="size-4" />
          )}
          Create workspace
        </Button>
      </form>

      <p className="mt-7 text-center text-sm text-[var(--ink-muted)]">
        Already have an account?{" "}
        <Link className="font-semibold text-[var(--accent)]" href="/login">
          Sign in
        </Link>
      </p>
    </>
  );
}
