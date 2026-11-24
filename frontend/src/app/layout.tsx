import type { Metadata } from "next";
import "./globals.css";
import { AppProvider } from "@/components/AppProvider";

export const metadata: Metadata = {
  title: "SVR Operations - Egypt Telecom Care",
  description:
    "Smart Voicemail Router for telecom customer-care operations: structured classification, explainable queue priority, and agent callback routing.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" dir="ltr" data-theme="light" suppressHydrationWarning>
      <body>
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
