"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useApp } from "@/components/AppProvider";
import { UI_COPY } from "@/lib/i18n";

export default function HomePage() {
  const { user, authLoading, locale } = useApp();
  const router = useRouter();
  const t = UI_COPY[locale];

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login");
    } else if (user.role === "agent") {
      router.replace("/my-tickets");
    } else {
      router.replace("/dashboard");
    }
  }, [authLoading, user, router]);

  return (
    <main className="main-content">
      <p className="loading-state">{t.loading}</p>
    </main>
  );
}
