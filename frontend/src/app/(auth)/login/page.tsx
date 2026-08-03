"use client";

import {zodResolver} from "@hookform/resolvers/zod";
import {AlertCircle, ArrowRight, Eye, EyeOff, LoaderCircle} from "lucide-react";
import Link from "next/link";
import {useRouter} from "next/navigation";
import {useState} from "react";
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
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: {errors, isSubmitting},
  } = useForm<Values>({resolver: zodResolver(schema)});

  const submit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await authFetch("/login", values);
      router.replace("/projects");
      router.refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to sign in";
      setFormError(message);
      toast.error(message);
    }
  });

  return (
    <>
      <p className="text-sm font-semibold text-[#ebe0d1]">Welcome back</p>
      <h1 className="mt-2 text-[32px] font-semibold leading-tight text-[#f5f1eb]">
        Sign in to RAGForge
      </h1>
      <p className="mt-3 text-[15px] leading-6 text-[#aaa39a]">
        Access your projects, documents, retrieval traces, and source-aware
        answers.
      </p>

      <form className="mt-8 space-y-5" onSubmit={submit} noValidate>
        <div>
          <label
            className="mb-2 block text-sm font-medium text-[#f5f1eb]"
            htmlFor="email"
          >
            Email address
          </label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? "email-error" : undefined}
            className="h-12 rounded-xl border-[#2a2825] bg-[#181715] px-4 text-base placeholder:text-[#777169] focus:border-[#c7b9a6] focus:ring-[#ebe0d1]/15"
            {...register("email")}
          />
          {errors.email ? (
            <span
              className="mt-2 block text-sm text-[#e36d65]"
              id="email-error"
            >
              {errors.email.message}
            </span>
          ) : null}
        </div>

        <div>
          <label
            className="mb-2 block text-sm font-medium text-[#f5f1eb]"
            htmlFor="password"
          >
            Password
          </label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Your password"
              aria-invalid={Boolean(errors.password)}
              aria-describedby={errors.password ? "password-error" : undefined}
              className="h-12 rounded-xl border-[#2a2825] bg-[#181715] px-4 pr-12 text-base placeholder:text-[#777169] focus:border-[#c7b9a6] focus:ring-[#ebe0d1]/15"
              {...register("password")}
            />
            <button
              type="button"
              className="absolute right-1.5 top-1.5 flex size-9 items-center justify-center rounded-lg text-[#aaa39a] transition hover:bg-[#25221f] hover:text-[#f5f1eb] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#c7b9a6] focus-visible:ring-offset-2 focus-visible:ring-offset-[#181715]"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((value) => !value)}
            >
              {showPassword ? (
                <EyeOff className="size-4" aria-hidden="true" />
              ) : (
                <Eye className="size-4" aria-hidden="true" />
              )}
            </button>
          </div>
          {errors.password ? (
            <span
              className="mt-2 block text-sm text-[#e36d65]"
              id="password-error"
            >
              {errors.password.message}
            </span>
          ) : null}
        </div>

        {formError ? (
          <div
            className="flex gap-2 rounded-xl border border-[#e36d65]/30 bg-[#e36d65]/10 px-3 py-2.5 text-sm leading-5 text-[#f2aaa5]"
            role="alert"
            aria-live="assertive"
          >
            <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{formError}</span>
          </div>
        ) : null}

        <Button
          className="h-12 w-full rounded-xl bg-[#ebe0d1] text-base font-semibold text-[#111111] hover:bg-[#fff7ec] focus-visible:ring-[#c7b9a6] focus-visible:ring-offset-[#070707]"
          size="lg"
          type="submit"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <ArrowRight className="size-4" aria-hidden="true" />
          )}
          Sign in
        </Button>
      </form>

      <p className="mt-7 text-center text-sm text-[#aaa39a]">
        New to RAGForge?{" "}
        <Link
          className="font-semibold text-[#ebe0d1] underline-offset-4 hover:text-[#fff7ec] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#c7b9a6] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0d0d0d]"
          href="/register"
        >
          Create an account
        </Link>
      </p>
    </>
  );
}
