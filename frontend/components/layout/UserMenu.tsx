"use client";
import { useRouter } from "next/navigation";
import { LogOut, Moon, Settings, Sun, User } from "lucide-react";
import { useTheme } from "next-themes";
import { toast } from "sonner";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuthStore } from "@/lib/stores/auth";

function initials(name: string | null | undefined, email: string): string {
  if (name) {
    const parts = name.trim().split(" ");
    return parts.length > 1
      ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
      : parts[0].slice(0, 2).toUpperCase();
  }
  return email.slice(0, 2).toUpperCase();
}

export function UserMenu() {
  const router            = useRouter();
  const { user, clearAuth } = useAuthStore();
  const { theme, setTheme } = useTheme();

  function handleLogout() {
    clearAuth();
    toast.success("Signed out successfully.");
    router.push("/login");
  }

  if (!user) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted transition-colors outline-none">
          <Avatar className="h-7 w-7">
            <AvatarFallback className="text-xs">{initials(user.full_name, user.email)}</AvatarFallback>
          </Avatar>
          <span className="hidden sm:block text-sm font-medium max-w-[120px] truncate">
            {user.full_name || user.email}
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        <DropdownMenuLabel className="font-normal">
          <p className="text-xs text-muted-foreground truncate">{user.email}</p>
          <p className="text-xs text-muted-foreground capitalize">{user.role}</p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push("/settings/account")}>
          <User className="h-4 w-4 mr-2" /> Profile
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => router.push("/settings/account")}>
          <Settings className="h-4 w-4 mr-2" /> Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark"
            ? <><Sun className="h-4 w-4 mr-2" /> Light mode</>
            : <><Moon className="h-4 w-4 mr-2" /> Dark mode</>
          }
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
          <LogOut className="h-4 w-4 mr-2" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
