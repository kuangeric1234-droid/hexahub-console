"use client";
import { PanelLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { UserMenu } from "./UserMenu";
import { useUIStore } from "@/lib/stores/ui";

export function Header() {
  const { toggleSidebar } = useUIStore();
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b bg-background/95 backdrop-blur px-4">
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 shrink-0"
        onClick={toggleSidebar}
        aria-label="Toggle sidebar"
      >
        <PanelLeft className="h-4 w-4" />
      </Button>
      <div className="flex-1" />
      <UserMenu />
    </header>
  );
}
