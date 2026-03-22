import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function riskTone(level: "low" | "medium" | "high" | "critical") {
  if (level === "critical") return "text-rose-300 bg-rose-500/15 border-rose-500/30";
  if (level === "high") return "text-orange-300 bg-orange-500/15 border-orange-500/30";
  if (level === "medium") return "text-amber-300 bg-amber-500/15 border-amber-500/30";
  return "text-emerald-300 bg-emerald-500/15 border-emerald-500/30";
}
