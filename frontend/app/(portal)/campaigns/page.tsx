"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { addWeeks, format } from "date-fns";
import { Plus, Loader2, CalendarDays, Sparkles, Pencil, ArrowRight, CheckCircle2, MoreHorizontal, Trash2, Eye } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import { Campaign } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";

const STATUS_VARIANT: Record<string, "default" | "success" | "warning" | "destructive" | "secondary"> = {
  draft:    "secondary", active:    "warning",  paused:   "default",
  completed:"success",   archived:  "secondary",
};

const PLATFORMS = [
  { value: "linkedin",       label: "LinkedIn",           flag: "🔵" },
  { value: "instagram",      label: "Instagram",          flag: "🟣" },
  { value: "blog",           label: "Blog",               flag: "📝" },
  { value: "xiaohongshu",    label: "Xiaohongshu 小红书",  flag: "🔴" },
  { value: "wechat_moments", label: "WeChat Moments 朋友圈",flag: "🟢" },
];

const WEEKS_OPTIONS = [4, 6, 8, 12, 16];

type DraftResult = {
  name: string; brief: string; objective: string;
  kpis: Record<string, number>;
  suggested_platforms: string[]; suggested_weeks: number; ai_generated: boolean;
};

function CampaignCard({ c, onClick, onDelete }: { c: Campaign; onClick: () => void; onDelete: () => void }) {
  return (
    <Card className="hover:shadow-md transition-shadow group">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle
            className="text-base leading-snug group-hover:text-primary transition-colors cursor-pointer flex-1"
            onClick={onClick}
          >
            {c.name}
          </CardTitle>
          <div className="flex items-center gap-1.5 shrink-0">
            <Badge variant={STATUS_VARIANT[c.status] ?? "default"} className="capitalize">
              {c.status}
            </Badge>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="flex h-6 w-6 items-center justify-center rounded hover:bg-muted transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-36">
                <DropdownMenuItem onClick={onClick}>
                  <Eye className="h-4 w-4 mr-2" /> View
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={(e) => { e.stopPropagation(); onDelete(); }}
                >
                  <Trash2 className="h-4 w-4 mr-2" /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground cursor-pointer" onClick={onClick}>
        <p className="line-clamp-2">{c.objective}</p>
        <div className="flex items-center gap-1 text-xs">
          <CalendarDays className="h-3 w-3" />
          {formatDate(c.start_date)} – {formatDate(c.end_date)}
        </div>
      </CardContent>
    </Card>
  );
}

function PlatformCheckbox({ value, label, flag, selected, onToggle }: {
  value: string; label: string; flag: string; selected: boolean; onToggle: () => void;
}) {
  return (
    <label className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
      selected ? "border-primary bg-primary/5 text-primary font-medium" : "border-border hover:bg-muted"
    }`}>
      <input type="checkbox" className="h-3.5 w-3.5 accent-primary"
        checked={selected} onChange={onToggle} />
      <span>{flag}</span>{label}
    </label>
  );
}

export default function CampaignsPage() {
  const router = useRouter();
  const qc     = useQueryClient();

  const [open, setOpen]     = useState(false);
  const [mode, setMode]     = useState<"ai" | "manual">("ai");

  // AI draft state
  const [prompt,    setPrompt]    = useState("");
  const [weeks,     setWeeks]     = useState(8);
  const [draft,     setDraft]     = useState<DraftResult | null>(null);
  const [draftPlats,setDraftPlats]= useState<string[]>([]);

  // Manual form state
  const BLANK = { name: "", brief: "", objective: "", start_date: "", end_date: "" };
  const [form,      setForm]      = useState(BLANK);
  const [manPlats,  setManPlats]  = useState<string[]>([]);

  function reset() {
    setPrompt(""); setDraft(null); setDraftPlats([]);
    setForm(BLANK); setManPlats([]);
    setMode("ai");
  }

  const [confirmDelete, setConfirmDelete] = useState<Campaign | null>(null);

  const { data: campaigns, isLoading } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn:  () => apiClient.get<Campaign[]>("/campaigns"),
  });

  // Delete campaign
  const deleteCampaign = useMutation({
    mutationFn: (id: string) => apiClient.del(`/campaigns/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      toast.success("Campaign deleted.");
      setConfirmDelete(null);
    },
    onError: (err: Error) => toast.error(err.message || "Failed to delete campaign."),
  });

  // Generate AI draft
  const generate = useMutation({
    mutationFn: (body: { prompt: string; weeks: number }) =>
      apiClient.post<DraftResult>("/campaigns/draft", body),
    onSuccess: (data) => {
      setDraft(data);
      setDraftPlats(data.suggested_platforms);
      if (!data.ai_generated) {
        toast.info("No API key connected — generated using a smart template. Edit freely before confirming.");
      } else {
        toast.success("Campaign brief generated by AI ✨ Review and edit before confirming.");
      }
    },
    onError: (err: Error) => toast.error(err.message || "Failed to generate draft."),
  });

  // Create campaign
  const create = useMutation({
    mutationFn: (body: object) => apiClient.post<Campaign>("/campaigns", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      toast.success("Campaign created! AI workflow is running in the background…");
      setOpen(false); reset();
    },
    onError: (err: Error) => toast.error(err.message || "Failed to create campaign."),
  });

  function confirmDraft() {
    if (!draft) return;
    if (draftPlats.length === 0) { toast.error("Select at least one platform."); return; }
    const today = new Date();
    const start = format(addWeeks(today, 1), "yyyy-MM-dd");
    const end   = format(addWeeks(today, 1 + draft.suggested_weeks), "yyyy-MM-dd");
    create.mutate({
      name: draft.name, brief: draft.brief, objective: draft.objective,
      kpis: draft.kpis, start_date: start, end_date: end, platforms: draftPlats,
    });
  }

  function submitManual(e: React.FormEvent) {
    e.preventDefault();
    if (manPlats.length === 0) { toast.error("Select at least one platform."); return; }
    create.mutate({
      name: form.name, brief: form.brief, objective: form.objective,
      kpis: {}, start_date: form.start_date, end_date: form.end_date, platforms: manPlats,
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Campaigns</h2>
        <Button size="sm" onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4 mr-1.5" /> New Campaign
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36 rounded-lg" />)}
        </div>
      ) : campaigns && campaigns.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((c) => (
            <CampaignCard
              key={c.id} c={c}
              onClick={() => router.push(`/campaigns/${c.id}`)}
              onDelete={() => setConfirmDelete(c)}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
          <CalendarDays className="h-10 w-10 text-muted-foreground opacity-30" />
          <div>
            <p className="text-sm font-medium">No campaigns yet</p>
            <p className="text-xs text-muted-foreground mt-1">Create your first campaign to start generating content.</p>
          </div>
          <Button size="sm" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4 mr-1.5" /> New Campaign
          </Button>
        </div>
      )}

      {/* ── Delete confirmation ─────────────────────────────────────────────── */}
      <Dialog open={!!confirmDelete} onOpenChange={(v) => { if (!v) setConfirmDelete(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete campaign?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            <strong className="text-foreground">{confirmDelete?.name}</strong> will be archived and removed from your campaigns list. This cannot be undone.
          </p>
          <div className="flex gap-2 justify-end mt-2">
            <Button variant="outline" onClick={() => setConfirmDelete(null)}>Cancel</Button>
            <Button
              variant="destructive"
              disabled={deleteCampaign.isPending}
              onClick={() => confirmDelete && deleteCampaign.mutate(confirmDelete.id)}
            >
              {deleteCampaign.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1.5" /> : <Trash2 className="h-4 w-4 mr-1.5" />}
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={open} onOpenChange={(v) => { if (!v) reset(); setOpen(v); }}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>New Campaign</DialogTitle>
          </DialogHeader>

          {/* Mode switcher */}
          <div className="flex gap-1 rounded-lg bg-muted p-1">
            <button
              onClick={() => setMode("ai")}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                mode === "ai" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Sparkles className="h-3.5 w-3.5" /> AI Draft
            </button>
            <button
              onClick={() => setMode("manual")}
              className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                mode === "manual" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Pencil className="h-3.5 w-3.5" /> Manual
            </button>
          </div>

          {/* ── AI DRAFT MODE ─────────────────────────────────────────────── */}
          {mode === "ai" && (
            <div className="space-y-4">
              {!draft ? (
                <>
                  <div className="space-y-1.5">
                    <Label>Describe your campaign</Label>
                    <Textarea
                      rows={3}
                      placeholder="e.g. Q3 property launch targeting young professionals in Melbourne, focus on the Box Hill development, bilingual EN/CN"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      className="resize-none"
                    />
                    <p className="text-xs text-muted-foreground">
                      One or two sentences — the AI will write the full brief, objective, and KPIs.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <Label>Campaign duration</Label>
                    <div className="flex gap-2 flex-wrap">
                      {WEEKS_OPTIONS.map((w) => (
                        <button key={w} onClick={() => setWeeks(w)}
                          className={`rounded-md border px-3 py-1 text-sm transition-colors ${
                            weeks === w ? "border-primary bg-primary/5 text-primary font-medium" : "border-border hover:bg-muted"
                          }`}>
                          {w} weeks
                        </button>
                      ))}
                    </div>
                  </div>

                  <Button
                    className="w-full gap-2"
                    onClick={() => generate.mutate({ prompt, weeks })}
                    disabled={generate.isPending || prompt.trim().length < 10}
                  >
                    {generate.isPending
                      ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating brief…</>
                      : <><Sparkles className="h-4 w-4" /> Generate Campaign Brief</>
                    }
                  </Button>
                </>
              ) : (
                /* Draft preview + edit */
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />
                    <p className="text-sm text-green-700 font-medium">
                      {draft.ai_generated ? "AI-generated brief ready" : "Template brief ready"}
                    </p>
                    <button className="ml-auto text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => setDraft(null)}>
                      ← Regenerate
                    </button>
                  </div>

                  <div className="space-y-1.5">
                    <Label>Campaign Name</Label>
                    <Input value={draft.name}
                      onChange={(e) => setDraft((d) => d ? { ...d, name: e.target.value } : d)} />
                  </div>

                  <div className="space-y-1.5">
                    <Label>Brief</Label>
                    <Textarea rows={4} className="text-sm resize-none" value={draft.brief}
                      onChange={(e) => setDraft((d) => d ? { ...d, brief: e.target.value } : d)} />
                  </div>

                  <div className="space-y-1.5">
                    <Label>Objective</Label>
                    <Textarea rows={2} className="text-sm resize-none" value={draft.objective}
                      onChange={(e) => setDraft((d) => d ? { ...d, objective: e.target.value } : d)} />
                  </div>

                  <div className="space-y-1.5">
                    <Label>KPIs</Label>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(draft.kpis).map(([key, val]) => (
                        <div key={key} className="space-y-0.5">
                          <p className="text-xs text-muted-foreground capitalize">{key.replace(/_/g, " ")}</p>
                          <Input
                            type="number" className="h-8 text-sm"
                            value={val}
                            onChange={(e) => setDraft((d) => d ? {
                              ...d, kpis: { ...d.kpis, [key]: Number(e.target.value) }
                            } : d)}
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  <Separator />

                  <div className="space-y-2">
                    <Label>Platforms <span className="text-xs text-muted-foreground">(select at least one)</span></Label>
                    <div className="grid grid-cols-2 gap-2">
                      {PLATFORMS.map(({ value, label, flag }) => (
                        <PlatformCheckbox key={value} value={value} label={label} flag={flag}
                          selected={draftPlats.includes(value)}
                          onToggle={() => setDraftPlats((p) =>
                            p.includes(value) ? p.filter((x) => x !== value) : [...p, value]
                          )} />
                      ))}
                    </div>
                  </div>

                  <Button className="w-full gap-2" onClick={confirmDraft} disabled={create.isPending}>
                    {create.isPending
                      ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating…</>
                      : <><ArrowRight className="h-4 w-4" /> Confirm & Start AI Workflow</>
                    }
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* ── MANUAL MODE ───────────────────────────────────────────────── */}
          {mode === "manual" && (
            <form onSubmit={submitManual} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="name">Name *</Label>
                <Input id="name" required value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="brief">Brief * <span className="text-xs text-muted-foreground">(min 20 chars)</span></Label>
                <Textarea id="brief" rows={3} required minLength={20} value={form.brief}
                  onChange={(e) => setForm((f) => ({ ...f, brief: e.target.value }))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="obj">Objective * <span className="text-xs text-muted-foreground">(min 10 chars)</span></Label>
                <Input id="obj" required minLength={10} value={form.objective}
                  onChange={(e) => setForm((f) => ({ ...f, objective: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Start Date *</Label>
                  <Input type="date" required value={form.start_date}
                    onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>End Date *</Label>
                  <Input type="date" required value={form.end_date}
                    onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Platforms *</Label>
                <div className="grid grid-cols-2 gap-2">
                  {PLATFORMS.map(({ value, label, flag }) => (
                    <PlatformCheckbox key={value} value={value} label={label} flag={flag}
                      selected={manPlats.includes(value)}
                      onToggle={() => setManPlats((p) =>
                        p.includes(value) ? p.filter((x) => x !== value) : [...p, value]
                      )} />
                  ))}
                </div>
              </div>
              <Button type="submit" className="w-full gap-2" disabled={create.isPending}>
                {create.isPending
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating…</>
                  : <><ArrowRight className="h-4 w-4" /> Create & Start AI Workflow</>
                }
              </Button>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
