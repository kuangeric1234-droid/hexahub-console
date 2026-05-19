"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { RefreshCw, Loader2, TrendingUp, Users, MousePointerClick, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Summary {
  total_reach:       number;
  total_engagement:  number;
  avg_ctr:           number;
  total_conversions: number;
  posts_tracked:     number;
  days:              number;
}

interface TimelinePoint {
  date:        string;
  reach:       number;
  engagement:  number;
  conversions: number;
}

interface PlatformRow {
  platform:    string;
  reach:       number;
  engagement:  number;
  conversions: number;
  posts:       number;
}

interface CampaignRow {
  campaign_id:   string;
  campaign_name: string;
  reach:         number;
  engagement:    number;
  conversions:   number;
  posts:         number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const PLATFORM_COLORS: Record<string, string> = {
  instagram:      "#e1306c",
  facebook:       "#1877f2",
  linkedin:       "#0077b5",
  blog:           "#6366f1",
  xiaohongshu:    "#ff2442",
  wechat_moments: "#07c160",
};

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, icon: Icon, color = "text-primary" }: {
  label: string; value: string; sub?: string;
  icon: React.ElementType; color?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-5 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold mt-0.5 tabular-nums">{value}</p>
            {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
          </div>
          <div className={`rounded-lg bg-muted/50 p-2 ${color}`}>
            <Icon className="h-4 w-4" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const DAY_OPTIONS = [7, 14, 30, 90];

export default function InsightsPage() {
  const qc   = useQueryClient();
  const [days, setDays] = useState(30);

  const { data: summary, isLoading: loadingSum } = useQuery<Summary>({
    queryKey: ["insights", "summary", days],
    queryFn:  () => apiClient.get(`/insights/summary?days=${days}`),
    staleTime: 5 * 60_000,
  });

  const { data: timeline, isLoading: loadingTime } = useQuery<{ points: TimelinePoint[] }>({
    queryKey: ["insights", "timeline", days],
    queryFn:  () => apiClient.get(`/insights/timeline?days=${days}`),
    staleTime: 5 * 60_000,
  });

  const { data: byPlatform, isLoading: loadingPlat } = useQuery<PlatformRow[]>({
    queryKey: ["insights", "by-platform", days],
    queryFn:  () => apiClient.get(`/insights/by-platform?days=${days}`),
    staleTime: 5 * 60_000,
  });

  const { data: byCampaign, isLoading: loadingCamp } = useQuery<CampaignRow[]>({
    queryKey: ["insights", "by-campaign", days],
    queryFn:  () => apiClient.get(`/insights/by-campaign?days=${days}`),
    staleTime: 5 * 60_000,
  });

  const sync = useMutation({
    mutationFn: () => apiClient.post<{ synced: number; message: string }>("/insights/sync"),
    onSuccess: (data) => {
      toast.success(data.message);
      qc.invalidateQueries({ queryKey: ["insights"] });
    },
    onError: (err: Error) => toast.error(err.message ?? "Sync failed"),
  });

  const isLoading = loadingSum || loadingTime || loadingPlat || loadingCamp;

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Insights</h2>
          {summary && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {summary.posts_tracked} posts tracked · last {days} days
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Day range selector */}
          <div className="flex rounded-md border overflow-hidden">
            {DAY_OPTIONS.map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  days === d
                    ? "bg-primary text-primary-foreground"
                    : "bg-background hover:bg-muted text-muted-foreground"
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
          <Button size="sm" variant="outline" className="gap-1.5"
            onClick={() => sync.mutate()} disabled={sync.isPending}>
            {sync.isPending
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <RefreshCw className="h-3.5 w-3.5" />}
            Sync
          </Button>
        </div>
      </div>

      {/* KPI cards */}
      {loadingSum ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      ) : summary ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="Total Reach"       value={fmt(summary.total_reach)}       icon={Users}              color="text-blue-500"   sub="unique accounts reached" />
          <KpiCard label="Total Engagement"  value={fmt(summary.total_engagement)}  icon={TrendingUp}         color="text-pink-500"   sub="likes + comments + shares" />
          <KpiCard label="Avg CTR"           value={`${(summary.avg_ctr * 100).toFixed(2)}%`} icon={MousePointerClick} color="text-amber-500" sub="click-through rate" />
          <KpiCard label="Conversions"       value={fmt(summary.total_conversions)} icon={Star}               color="text-green-500"  sub="saves / leads" />
        </div>
      ) : (
        <div className="rounded-lg border border-dashed p-10 text-center">
          <TrendingUp className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
          <p className="text-sm font-medium">No metrics yet</p>
          <p className="text-xs text-muted-foreground mt-1 mb-4">
            Click Sync to pull post performance from Meta, or wait for the daily sync at 06:30 UTC.
          </p>
          <Button size="sm" onClick={() => sync.mutate()} disabled={sync.isPending} className="gap-1.5">
            {sync.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Sync now
          </Button>
        </div>
      )}

      {/* Timeline chart */}
      {(timeline?.points?.length ?? 0) > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Reach & Engagement over time</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={timeline!.points} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={fmt} width={40} />
                <Tooltip formatter={(v: number) => fmt(v)} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="reach"      stroke="#3b82f6" strokeWidth={2} dot={false} name="Reach" />
                <Line type="monotone" dataKey="engagement" stroke="#ec4899" strokeWidth={2} dot={false} name="Engagement" />
                <Line type="monotone" dataKey="conversions"stroke="#22c55e" strokeWidth={2} dot={false} name="Conversions" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">

        {/* Platform breakdown */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">By Platform</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingPlat ? (
              <Skeleton className="h-40 rounded-lg" />
            ) : !byPlatform?.length ? (
              <p className="text-xs text-muted-foreground text-center py-8">No platform data yet</p>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={byPlatform} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="platform" tick={{ fontSize: 10 }} tickFormatter={(v) => v.replace("_", " ")} />
                    <YAxis tick={{ fontSize: 10 }} tickFormatter={fmt} width={36} />
                    <Tooltip formatter={(v: number) => fmt(v)} />
                    <Bar dataKey="reach" name="Reach" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="engagement" name="Engagement" fill="#ec4899" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-3 space-y-1.5">
                  {byPlatform.map((p) => (
                    <div key={p.platform} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full shrink-0"
                          style={{ backgroundColor: PLATFORM_COLORS[p.platform] ?? "#64748b" }} />
                        <span className="capitalize">{p.platform.replace("_", " ")}</span>
                        <Badge variant="secondary" className="text-[10px] h-4">{p.posts} posts</Badge>
                      </div>
                      <span className="text-muted-foreground">{fmt(p.reach)} reach</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Campaign breakdown */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">By Campaign</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingCamp ? (
              <Skeleton className="h-40 rounded-lg" />
            ) : !byCampaign?.length ? (
              <p className="text-xs text-muted-foreground text-center py-8">No campaign data yet</p>
            ) : (
              <div className="space-y-3">
                {byCampaign.slice(0, 8).map((c) => {
                  const maxReach = Math.max(...byCampaign.map(x => x.reach), 1);
                  const pct      = Math.round((c.reach / maxReach) * 100);
                  return (
                    <div key={c.campaign_id} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-medium truncate flex-1 mr-3">{c.campaign_name}</span>
                        <span className="text-muted-foreground shrink-0">
                          {fmt(c.reach)} · {fmt(c.engagement)} eng
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
