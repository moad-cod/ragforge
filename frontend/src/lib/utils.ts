import {clsx, type ClassValue} from "clsx";
import {formatDistanceToNow} from "date-fns";
import {twMerge} from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function relativeTime(value: string | Date) {
  return formatDistanceToNow(new Date(value), {addSuffix: true});
}

export function formatLatency(value: number | null) {
  if (value === null) return "—";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(1)} s`;
}

export function initials(name: string | null | undefined, email: string) {
  const source = name?.trim() || email;
  return source
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
