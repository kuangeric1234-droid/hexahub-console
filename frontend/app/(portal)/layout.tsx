import { Sidebar } from "@/components/layout/Sidebar";
import { Header }  from "@/components/layout/Header";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
