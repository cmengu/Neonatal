import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NeonatalGuard",
  description: "NICU early-warning dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-slate-900 text-slate-100">{children}</body>
    </html>
  );
}
