"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Loader2, Pause, Play, RefreshCw, TrendingUp,
  DollarSign, Users, MousePointerClick, MoreHorizontal,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { apiClient } from "@/lib/api";
import { AdCampaign, AdInsights, CreateAdCampaignRequest } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { toast } from "sonner";

const STATUS_VARIANT: Record<string, "default" | "success" | "warning" | "destructive" | "secondary"> = {
  PAUSED:   "secondary",
  ACTIVE:   "success",
  ARCHIVED: "default",
  DELETED:  "destructive",
};

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border bg-card px-4 py-3 space-y-0.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

function InsightsPanel({ ad }: { ad: AdCampaign }) {
  const { data, isLoading, isError } = useQuery<AdInsights>({
    queryKey: ["ad-insights", ad.id],
    queryFn:  () => apiClient.get<AdInsights>(`/ads/meta/campaigns/${ad.id}/insights`),
    staleTime: 5 * 60_000,
    retry: false,
  });

  if (isLoading) return <div className="flex gap-3 mt-3">{Array.from({length: 4}).map((_,i) => <Skeleton key={i} className="h-16 flex-1 rounded-lg" />)}</div>;
  if (isError || !data)  return <p className="text-xs text-muted-foreground mt-3">Insights unavailable — sync or check Meta connection.</p>;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3">
      <StatCard label="Leads"       value={data.leads}                              sub={`CPL $${data.cpl_aud.toFixed(2)}`} />
      <StatCard label="Spend (AUD)" value={`$${data.spend_aud.toFixed(2)}`}        sub="last 30 days" />
      <StatCard label="CTR"         value={`${data.ctr.toFixed(2)}%`}              sub={`${data.clicks.toLocaleString()} clicks`} />
      <StatCard label="Reach"       value={data.reach.toLocaleString()}             sub={`${data.impressions.toLocaleString()} impressions`} />
    </div>
  );
}

function AdCampaignRow({
  ad,
  onPause,
  onResume,
  onSync,
  mutating,
}: {
  ad:       AdCampaign;
  onPause:  (id: string) => void;
  onResume: (id: string) => void;
  onSync:   (id: string) => void;
  mutating: boolean;
}) {
  const [showInsights, setShowInsights] = useState(false);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="space-y-0.5 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-medium text-sm truncate">{ad.meta_campaign_id}</p>
              <Badge variant={STATUS_VARIANT[ad.status] ?? "default"}>{ad.status}</Badge>
            </div>
            <p className="text-xs text-muted-foreground">{ad.targeting_summary ?? "No targeting set"}</p>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {ad.status === "ACTIVE" ? (
              <Button size="sm" variant="outline" className="gap-1.5 h-7 text-xs"
                disabled={mutating} onClick={() => onPause(ad.id)}>
                {mutating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Pause className="h-3 w-3" />}
                Pause
              </Button>
            ) : (
              <Button size="sm" variant="outline" className="gap-1.5 h-7 text-xs"
                disabled={mutating} onClick={() => onResume(ad.id)}>
                {mutating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                Activate
              </Button>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex h-7 w-7 items-center justify-center rounded hover:bg-muted transition-colors">
                  <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-36">
                <DropdownMenuItem onClick={() => setShowInsights(!showInsights)}>
                  <TrendingUp className="h-4 w-4 mr-2" /> {showInsights ? "Hide" : "Show"} insights
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onSync(ad.id)} disabled={mutating}>
                  <RefreshCw className="h-4 w-4 mr-2" /> Sync metrics
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <DollarSign className="h-3 w-3" />
            {ad.daily_budget_aud != null ? `$${ad.daily_budget_aud}/day AUD` : "Budget not set"}
          </span>
          <span className="flex items-center gap-1">
            <MousePointerClick className="h-3 w-3" />
            {ad.objective ?? "OUTCOME_LEADS"}
          </span>
          {ad.synced_at && (
            <span className="flex items-center gap-1">
              <RefreshCw className="h-3 w-3" />
              Synced {formatDateTime(ad.synced_at)}
            </span>
          )}
        </div>

        {showInsights && (
          <>
            <Separator className="mt-3" />
            <InsightsPanel ad={ad} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

function CreateCampaignDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<CreateAdCampaignRequest>({
    name:                "",
    daily_budget_aud:    50,
    targeting_location:  "AU",
    targeting_interests: "",
  });

  const create = useMutation({
    mutationFn: (body: CreateAdCampaignRequest) =>
      apiClient.post<AdCampaign>("/ads/meta/campaigns", body),
    onSuccess: () => {
      toast.success("Campaign created and set to PAUSED — activate when ready");
      qc.invalidateQueries({ queryKey: ["ad-campaigns"] });
      onClose();
      setForm({ name: "", daily_budget_aud: 50, targeting_location: "AU", targeting_interests: "" });
    },
    onError: (err: Error) => toast.error(err.message ?? "Failed to create campaign"),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { toast.error("Campaign name is required"); return; }
    if (form.daily_budget_aud <= 0) { toast.error("Daily budget must be greater than 0"); return; }
    create.mutate(form);
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Create Meta Ads Campaign</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <Label>Campaign name</Label>
            <Input
              placeholder="e.g. Hexa Hub Q3 Lead Gen"
              value={form.name}
              onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))}
            />
          </div>

          <div className="space-y-1.5">
            <Label>Daily budget (AUD)</Label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">$</span>
              <Input
                type="number" min="1" step="1" className="pl-7"
                placeholder="50"
                value={form.daily_budget_aud}
                onChange={(e) => setForm(f => ({ ...f, daily_budget_aud: parseFloat(e.target.value) || 0 }))}
              />
            </div>
            <p className="text-xs text-muted-foreground">Australian dollars per day. Campaign starts PAUSED.</p>
          </div>

          <div className="space-y-1.5">
            <Label>Targeting location</Label>
            <Input
              placeholder="AU"
              value={form.targeting_location}
              onChange={(e) => setForm(f => ({ ...f, targeting_location: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground">ISO country code(s), comma-separated (e.g. AU, NZ)</p>
          </div>

          <div className="space-y-1.5">
            <Label>Targeting interests <span className="text-muted-foreground">(optional)</span></Label>
            <Input
              placeholder="Business, Marketing, Cross-border trade"
              value={form.targeting_interests}
              onChange={(e) => setForm(f => ({ ...f, targeting_interests: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground">Stored as summary — used for reference, not passed to Meta API directly.</p>
          </div>

          <div className="flex gap-2 pt-2">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1 gap-1.5" disabled={create.isPending}>
              {create.isPending
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating…</>
                : <><Plus className="h-4 w-4" /> Create (Paused)</>}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function AdsPage() {
  const qc              = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [mutatingId,  setMutatingId]  = useState<string | null>(null);

  const { data: campaigns, isLoading } = useQuery<AdCampaign[]>({
    queryKey: ["ad-campaigns"],
    queryFn:  () => apiClient.get<AdCampaign[]>("/ads/meta/campaigns"),
    refetchInterval: 60_000,
  });

  const pause = useMutation({
    mutationFn: (id: string) => apiClient.post(`/ads/meta/campaigns/${id}/pause`),
    onMutate:   (id) => setMutatingId(id),
    onSuccess:  () => { toast.success("Campaign paused"); qc.invalidateQueries({ queryKey: ["ad-campaigns"] }); },
    onError:    (err: Error) => toast.error(err.message ?? "Failed to pause"),
    onSettled:  () => setMutatingId(null),
  });

  const resume = useMutation({
    mutationFn: (id: string) => apiClient.post(`/ads/meta/campaigns/${id}/resume`),
    onMutate:   (id) => setMutatingId(id),
    onSuccess:  () => { toast.success("Campaign activated — it is now spending"); qc.invalidateQueries({ queryKey: ["ad-campaigns"] }); },
    onError:    (err: Error) => toast.error(err.message ?? "Failed to activate"),
    onSettled:  () => setMutatingId(null),
  });

  const sync = useMutation({
    mutationFn: (id: string) => apiClient.post(`/ads/meta/campaigns/${id}/sync`),
    onMutate:   (id) => setMutatingId(id),
    onSuccess:  () => { toast.success("Metrics synced"); qc.invalidateQueries({ queryKey: ["ad-campaigns"] }); },
    onError:    (err: Error) => toast.error(err.message ?? "Sync failed"),
    onSettled:  () => setMutatingId(null),
  });

  const active = campaigns?.filter(c => c.status === "ACTIVE").length ?? 0;
  const paused = campaigns?.filter(c => c.status === "PAUSED").length ?? 0;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Meta Ads</h2>
          {campaigns && campaigns.length > 0 && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {active} active · {paused} paused · {campaigns.length} total
            </p>
          )}
        </div>
        <Button size="sm" className="gap-1.5" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" /> New Campaign
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />)}
        </div>
      ) : !campaigns || campaigns.length === 0 ? (
        <div className="rounded-lg border border-dashed p-10 text-center">
          <Users className="h-8 w-8 mx-auto text-muted-foreground/40 mb-3" />
          <p className="text-sm font-medium">No Meta Ads campaigns yet</p>
          <p className="text-xs text-muted-foreground mt-1 mb-4">
            Create a lead generation campaign — it starts PAUSED and won't spend until you activate it.
          </p>
          <Button size="sm" className="gap-1.5" onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" /> Create first campaign
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {campaigns.map((ad) => (
            <AdCampaignRow
              key={ad.id}
              ad={ad}
              mutating={mutatingId === ad.id}
              onPause={(id)  => pause.mutate(id)}
              onResume={(id) => resume.mutate(id)}
              onSync={(id)   => sync.mutate(id)}
            />
          ))}
        </div>
      )}

      <CreateCampaignDialog open={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  );
}
