"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home, CalendarDays, Megaphone, Palette, Linkedin, BookOpen, Instagram,
  Flower2, MessageCircle, Tv2, CheckSquare, Send, Package, Plug, BarChart2,
  Image, Shield, Users, ActivitySquare, Zap, ChevronDown, ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/stores/ui";
import { useApprovalCount } from "@/lib/hooks/use-approval-count";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";

type NavItem = { href: string; label: string; icon: React.ElementType; adminOnly?: boolean; badge?: boolean };
type NavSection = { label?: string; items: NavItem[]; collapsible?: boolean };

const NAV: NavSection[] = [
  {
    items: [{ href: "/", label: "Home", icon: Home }],
  },
  {
    label: "PLAN",
    items: [
      { href: "/calendar",  label: "Calendar",  icon: CalendarDays },
      { href: "/campaigns", label: "Campaigns", icon: Megaphone    },
      { href: "/brand",     label: "Brand Kit", icon: Palette      },
    ],
  },
  {
    label: "CREATE",
    collapsible: true,
    items: [
      { href: "/create/linkedin",       label: "LinkedIn Post",    icon: Linkedin       },
      { href: "/create/blog",           label: "Blog Post",        icon: BookOpen       },
      { href: "/create/instagram",      label: "Instagram Post",   icon: Instagram      },
      { href: "/create/xiaohongshu",    label: "Xiaohongshu",      icon: Flower2        },
      { href: "/create/wechat-moments", label: "WeChat Moments",   icon: MessageCircle  },
      { href: "/create/ad-creative",    label: "Ad Creative",      icon: Tv2            },
    ],
  },
  {
    label: "APPROVE",
    items: [{ href: "/approvals", label: "Approvals", icon: CheckSquare, badge: true }],
  },
  {
    label: "PUBLISH",
    items: [
      { href: "/publish/scheduled",    label: "Scheduled",          icon: Send    },
      { href: "/publish/packages",     label: "Publishing Packages", icon: Package },
      { href: "/publish/integrations", label: "Integrations",        icon: Plug    },
    ],
  },
  {
    label: "MEASURE",
    items: [{ href: "/insights", label: "Insights", icon: BarChart2 }],
  },
  {
    label: "ASSETS",
    items: [{ href: "/assets", label: "Media Library", icon: Image }],
  },
  {
    label: "TOOLS",
    items: [{ href: "/tools/compliance-checker", label: "Compliance Checker", icon: Shield }],
  },
  {
    label: "SETTINGS",
    items: [
      { href: "/settings/team",    label: "Team",         icon: Users,          adminOnly: true },
      { href: "/settings/account", label: "Account",      icon: Users                          },
      { href: "/logs",             label: "Activity Log", icon: ActivitySquare, adminOnly: true },
    ],
  },
];

function NavLink({
  item,
  collapsed,
  count,
}: {
  item: NavItem;
  collapsed: boolean;
  count?: number;
}) {
  const pathname = usePathname();
  const active   = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));

  return (
    <Link
      href={item.href}
      title={collapsed ? item.label : undefined}
      className={cn(
        "group flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
        collapsed && "justify-center px-0",
        active
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      )}
    >
      <item.icon className="h-4 w-4 shrink-0" />
      {!collapsed && (
        <>
          <span className="flex-1 truncate">{item.label}</span>
          {item.badge && count !== undefined && count > 0 && (
            <Badge variant="destructive" className="h-4 min-w-[1rem] px-1 text-[10px]">
              {count > 99 ? "99+" : count}
            </Badge>
          )}
        </>
      )}
    </Link>
  );
}

export function Sidebar() {
  const { sidebarCollapsed }    = useUIStore();
  const { data: approvalCount } = useApprovalCount();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  return (
    <aside
      className={cn(
        "flex h-screen shrink-0 flex-col border-r bg-card overflow-hidden sidebar-transition",
        sidebarCollapsed ? "w-14" : "w-56"
      )}
    >
      {/* Logo */}
      <div className={cn(
        "flex h-12 shrink-0 items-center border-b",
        sidebarCollapsed ? "justify-center px-0" : "gap-2 px-4"
      )}>
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary">
          <Zap className="h-4 w-4 text-primary-foreground" />
        </div>
        {!sidebarCollapsed && (
          <span className="font-semibold text-sm tracking-tight">Hexa Hub</span>
        )}
      </div>

      {/* Nav */}
      <nav className={cn("flex-1 overflow-y-auto py-3 space-y-4", sidebarCollapsed ? "px-1.5" : "px-2")}>
        {NAV.map((section, si) => {
          const sectionKey    = section.label ?? String(si);
          const isCollapsed   = collapsed[sectionKey];
          const hasActiveItem = section.items.some((it) => {
            const p = typeof window !== "undefined" ? window.location.pathname : "";
            return p === it.href || (it.href !== "/" && p.startsWith(it.href));
          });

          return (
            <div key={sectionKey}>
              {section.label && !sidebarCollapsed && (
                <button
                  onClick={() => section.collapsible && setCollapsed((c) => ({ ...c, [sectionKey]: !c[sectionKey] }))}
                  className={cn(
                    "flex w-full items-center justify-between px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60",
                    section.collapsible && "hover:text-muted-foreground cursor-pointer"
                  )}
                >
                  {section.label}
                  {section.collapsible && (
                    isCollapsed && !hasActiveItem
                      ? <ChevronRight className="h-3 w-3" />
                      : <ChevronDown className="h-3 w-3" />
                  )}
                </button>
              )}
              {(!section.collapsible || !isCollapsed || hasActiveItem) && (
                <div className="space-y-0.5">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.href}
                      item={item}
                      collapsed={sidebarCollapsed}
                      count={item.badge ? approvalCount : undefined}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
