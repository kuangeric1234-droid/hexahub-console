"use client";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Megaphone, CheckSquare, Bot, BarChart2, ArrowRight,
  Linkedin, BookOpen, Instagram, Flower2, Tv2,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { KpiCard } from "@/components/shared/KpiCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listCampaigns } from "@/lib/api/campaigns";
import { getApprovalCount } from "@/lib/api/approvals";
import { listAgentLogs } from "@/lib/api/logs";
import { useAuthStore } from "@/lib/stores/auth";
import { APPROVAL_POLL_INTERVAL_MS } from "@/lib/constants";
import { PLATFORMS, type PlatformKey } from "@/lib/constants";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

const QUICK_ACTIONS = [
  { label: "New Campaign",        href: "/campaigns/new", icon: Megaphone   },
  { label: "LinkedIn Post",       href: "/create/linkedin",    icon: Linkedin    },
  { label: "Instagram Post",      href: "/create/instagram",   icon: Instagram   },
  { label: "Xiaohongshu Post",    href: "/create/xiaohongshu", icon: Flower2     },
  { label: "Ad Creative",         href: "/create/ad-creative", icon: Tv2         },
  { label: "Blog Post",           href: "/create/blog",        icon: BookOpen    },
];

export default function DashboardPage() {
  const router       = useRouter();
  const { user }     = useAuthStore();

  const { data: campaigns, isLoading: loadingCampaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn:  () => listCampaigns({ page_size: 100 }),
  });

  const { data: approvalCount } = useQuery({
    queryKey:       ["approvals", "count"],
    queryFn:        getApprovalCount,
    refetchInterval: APPROVAL_POLL_INTERVAL_MS,
    retry:          false,
    select:         (d) => d.count,
  });

  const { data: recentLogs, isLoading: loadingLogs } = useQuery({
    queryKey: ["agent-logs", "recent"],
    queryFn:  () => listAgentLogs({ page_size: 10 }),
    retry:    false,
  });

  const activeCampaigns = campaigns?.filter((c) => c.status === "active").length ?? 0;

  return (
    <div className="space-y-6">
      {/* Greeting */}
      <div>
        <h1 className="text-xl font-semibold">
          {greeting()}{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""} 👋
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Here&apos;s what&apos;s happening with your campaigns today.
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard
          label="Active Campaigns"
          value={loadingCampaigns ? "—" : activeCampaigns}
          icon={Megaphone}
          loading={loadingCampaigns}
          sub="currently running"
        />
        <KpiCard
          label="Pending Approvals"
          value={approvalCount ?? "—"}
          icon={CheckSquare}
          sub="awaiting your review"
        />
        <KpiCard
          label="Total Campaigns"
          value={campaigns?.length ?? "—"}
          icon={BarChart2}
          loading={loadingCampaigns}
          sub="all time"
        />
        <KpiCard
          label="AI Agents"
          value={recentLogs?.length ?? "—"}
          icon={Bot}
          loading={loadingLogs}
          sub="runs logged"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Quick Actions */}
        <Card className="lg:col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 p-3 pt-0">
            {QUICK_ACTIONS.map(({ label, href, icon: Icon }) => (
              <button
                key={href}
                onClick={() => router.push(href)}
                className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{label}</span>
                <ArrowRight className="h-3.5 w-3.5 ml-auto opacity-0 group-hover:opacity-100" />
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Recent Campaigns */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-sm font-semibold">Recent Campaigns</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => router.push("/campaigns")} className="text-xs h-7">
              View all
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {loadingCampaigns ? (
              <div className="space-y-2 p-4">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 rounded" />)}
              </div>
            ) : !campaigns || campaigns.length === 0 ? (
              <EmptyState
                icon={Megaphone}
                title="No campaigns yet"
                description="Create your first campaign to start generating content."
                action={{ label: "New Campaign", onClick: () => router.push("/campaigns/new") }}
              />
            ) : (
              <div className="divide-y">
                {campaigns.slice(0, 5).map((c) => (
                  <button
                    key={c.id}
                    onClick={() => router.push(`/campaigns/${c.id}`)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{c.name}</p>
                      <p className="text-xs text-muted-foreground truncate">{c.objective}</p>
                    </div>
                    <Badge
                      variant={c.status === "active" ? "warning" : c.status === "completed" ? "success" : "secondary"}
                      className="shrink-0 capitalize text-[10px]"
                    >
                      {c.status}
                    </Badge>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Agent Activity */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-sm font-semibold">Recent Agent Activity</CardTitle>
          {user?.role === "admin" && (
            <Button variant="ghost" size="sm" onClick={() => router.push("/logs")} className="text-xs h-7">
              View all
            </Button>
          )}
        </CardHeader>
        <CardContent className="p-0">
          {loadingLogs ? (
            <div className="space-y-2 p-4">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 rounded" />)}
            </div>
          ) : !recentLogs || recentLogs.length === 0 ? (
            <EmptyState
              icon={Bot}
              title="No agent activity yet"
              description="Agent runs appear here once you create a campaign."
            />
          ) : (
            <div className="divide-y">
              {recentLogs.slice(0, 8).map((log) => (
                <div key={log.id} className="flex items-center gap-3 px-4 py-2.5">
                  <div className={`h-2 w-2 rounded-full shrink-0 ${
                    log.status === "success" ? "bg-green-500"
                    : log.status === "failed"  ? "bg-red-500"
                    : "bg-amber-500"
                  }`} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-muted-foreground">{log.agent_name}</span>
                    <span className="text-xs text-muted-foreground ml-2">· {log.task}</span>
                  </div>
                  {log.timestamp && (
                    <span className="text-xs text-muted-foreground shrink-0">
                      {formatDistanceToNow(new Date(log.timestamp), { addSuffix: true })}
                    </span>
                  )}
                  {log.duration_ms && (
                    <span className="text-xs text-muted-foreground shrink-0">
                      {(log.duration_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
