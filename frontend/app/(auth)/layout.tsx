import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sign In" };

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      {children}
    </div>
  );
}
