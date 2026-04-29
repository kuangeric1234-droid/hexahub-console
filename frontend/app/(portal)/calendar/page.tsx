"use client";
import { useState, useCallback } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Calendar, dateFnsLocalizer, Views } from "react-big-calendar";
import withDragAndDrop from "react-big-calendar/lib/addons/dragAndDrop";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { enUS } from "date-fns/locale";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { CalendarDays, Plus, Save, Wand2, Loader2, MessageSquare } from "lucide-react";
import { api } from "@/lib/api/client";
import { apiClient } from "@/lib/api";
import { Campaign, CampaignCalendar, PostSlot } from "@/lib/types";
import { format as fmt } from "date-fns";
import "react-big-calendar/lib/css/react-big-calendar.css";
import "react-big-calendar/lib/addons/dragAndDrop/styles.css";
import { toast } from "sonner";

const DnDCalendar = withDragAndDrop(Calendar);

const localizer = dateFnsLocalizer({
  format, parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 1 }),
  getDay,
  locales: { "en-US": enUS },
});

const PLATFORM_COLORS: Record<string, string> = {
  linkedin:       "#0077b5",
  instagram:      "#e1306c",
  facebook:       "#1877f2",
  blog:           "#6366f1",
  xiaohongshu:    "#ff2442",
  wechat_moments: "#07c160",
};

const PLATFORMS = [
  { value: "linkedin",       label: "LinkedIn" },
  { value: "instagram",      label: "Instagram" },
  { value: "facebook",       label: "Facebook" },
  { value: "blog",           label: "Blog" },
  { value: "xiaohongshu",    label: "Xiaohongshu" },
  { value: "wechat_moments", label: "WeChat Moments" },
];

type CalEvent = {
  id:       string;
  title:    string;
  start:    Date;
  end:      Date;
  platform: string;
  post:     PostSlot;
};

function buildEvents(data: CampaignCalendar): CalEvent[] {
  return data.posts
    .filter((p): p is PostSlot & { scheduled_at: string } => !!p.scheduled_at)
    .map((p) => {
      const start = new Date(p.scheduled_at);
      const end   = new Date(start.getTime() + 30 * 60_000);
      return {
        id: p.id, title: `${p.platform.replace("_", " ")} — ${p.copy ? p.copy.slice(0, 30) + "…" : "Draft"}`,
        start, end, platform: p.platform, post: p,
      };
    });
}

// ── Post detail modal ─────────────────────────────────────────────────────────

function PostModal({ post, open, onClose, onSaved }: {
  post: PostSlot; open: boolean; onClose: () => void; onSaved: (u: Partial<PostSlot>) => void;
}) {
  const [copy,       setCopy]       = useState(post.copy ?? "");
  const [note,       setNote]       = useState((post.metadata_json?.personal_note as string) ?? "");
  const [aiPrompt,   setAiPrompt]   = useState("");
  const [savingCopy, setSavingCopy] = useState(false);
  const [savingNote, setSavingNote] = useState(false);
  const [rewriting,  setRewriting]  = useState(false);

  async function handleSaveCopy() {
    setSavingCopy(true);
    try { await apiClient.patch(`/posts/${post.id}`, { copy }); toast.success("Copy saved"); onSaved({ copy }); }
    catch { toast.error("Save failed"); }
    finally { setSavingCopy(false); }
  }

  async function handleSaveNote() {
    setSavingNote(true);
    try {
      await apiClient.patch(`/posts/${post.id}`, { metadata_json: { ...post.metadata_json, personal_note: note } } as any);
      toast.success("Note saved");
    } catch { toast.error("Save failed"); }
    finally { setSavingNote(false); }
  }

  async function handleAiRewrite() {
    if (!aiPrompt.trim()) return;
    setRewriting(true);
    try {
      const result = await apiClient.post<{ copy: string }>(`/posts/${post.id}/modify`, { instructions: aiPrompt });
      setCopy(result.copy); setAiPrompt(""); toast.success("Copy updated");
    } catch { toast.error("Rewrite failed"); }
    finally { setRewriting(false); }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: PLATFORM_COLORS[post.platform] ?? "#64748b" }} />
            <span className="capitalize">{post.platform.replace("_", " ")}</span>
            <Badge variant={post.approval_status === "approved" ? "default" : post.approval_status === "rejected" ? "destructive" : "secondary"} className="text-xs ml-1">
              {post.approval_status}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {post.scheduled_at && (
          <p className="text-xs text-muted-foreground -mt-2">
            📅 {fmt(new Date(post.scheduled_at), "EEEE, MMMM d yyyy 'at' h:mm a")}
          </p>
        )}

        <div className="space-y-2">
          <Label>Post copy</Label>
          <Textarea rows={8} value={copy} onChange={(e) => setCopy(e.target.value)} className="text-sm font-mono resize-y" placeholder="No copy yet…" />
          <Button size="sm" onClick={handleSaveCopy} disabled={savingCopy} className="gap-1.5">
            {savingCopy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save copy
          </Button>
        </div>

        <Separator />
        <div className="space-y-2">
          <Label className="flex items-center gap-1.5"><Wand2 className="h-3.5 w-3.5" /> Modify with AI</Label>
          <div className="flex gap-2">
            <Input value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
              placeholder="e.g. Add 3 hashtags, make it punchier…" className="text-sm"
              onKeyDown={(e) => { if (e.key === "Enter") handleAiRewrite(); }} />
            <Button size="sm" onClick={handleAiRewrite} disabled={rewriting || !aiPrompt.trim()}>
              {rewriting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Rewrite"}
            </Button>
          </div>
        </div>

        <Separator />
        <div className="space-y-2">
          <Label className="flex items-center gap-1.5"><MessageSquare className="h-3.5 w-3.5" /> Personal notes</Label>
          <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Private notes — only visible to you…" className="text-sm" />
          <Button size="sm" variant="outline" onClick={handleSaveNote} disabled={savingNote} className="gap-1.5">
            {savingNote ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save note
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Add post modal ────────────────────────────────────────────────────────────

function AddPostModal({ open, campaignId, onClose, onAdded }: {
  open: boolean; campaignId: string; onClose: () => void; onAdded: () => void;
}) {
  const [platform,    setPlatform]    = useState("linkedin");
  const [scheduledAt, setScheduledAt] = useState("");
  const [copy,        setCopy]        = useState("");
  const [aiPrompt,    setAiPrompt]    = useState("");
  const [generating,  setGenerating]  = useState(false);
  const [saving,      setSaving]      = useState(false);

  async function handleGenerate() {
    if (!aiPrompt.trim()) return;
    setGenerating(true);
    try {
      const result = await apiClient.post<{ copy: string }>("/create/assisted", { platform, brief: aiPrompt });
      setCopy(result.copy); toast.success("Copy generated");
    } catch { toast.error("Generation failed"); }
    finally { setGenerating(false); }
  }

  async function handleSave() {
    if (!copy.trim() || !scheduledAt) { toast.error("Add copy and a scheduled date first"); return; }
    setSaving(true);
    try {
      await apiClient.post("/posts", { campaign_id: campaignId, platform, copy, scheduled_at: new Date(scheduledAt).toISOString(), status: "draft" });
      toast.success("Post added"); onAdded(); onClose();
      setCopy(""); setAiPrompt(""); setScheduledAt(""); setPlatform("linkedin");
    } catch { toast.error("Failed to add post"); }
    finally { setSaving(false); }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Add post</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>Platform</Label>
              <select className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={platform} onChange={(e) => setPlatform(e.target.value)}>
                {PLATFORMS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Scheduled date & time</Label>
              <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="flex items-center gap-1.5"><Wand2 className="h-3.5 w-3.5" /> Generate with AI</Label>
            <div className="flex gap-2">
              <Input value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="Describe what this post should be about…" className="text-sm" />
              <Button size="sm" onClick={handleGenerate} disabled={generating || !aiPrompt.trim()}>
                {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Generate"}
              </Button>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Copy</Label>
            <Textarea rows={6} value={copy} onChange={(e) => setCopy(e.target.value)}
              placeholder="Write or generate post copy…" className="text-sm" />
          </div>

          <Button className="w-full gap-1.5" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add post to calendar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const [selectedId,   setSelectedId]   = useState<string>("");
  const [selectedPost, setSelectedPost] = useState<PostSlot | null>(null);
  const [addOpen,      setAddOpen]      = useState(false);
  const [calDate,      setCalDate]      = useState(new Date());

  const { data: campaigns, isLoading: loadingCampaigns } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn:  async () => (await api.get<Campaign[]>("/campaigns")).data,
  });

  const { data: calData, isLoading: loadingCal, refetch } = useQuery<CampaignCalendar>({
    queryKey: ["calendar", selectedId],
    queryFn:  async () => (await api.get<CampaignCalendar>(`/campaigns/${selectedId}/calendar`)).data,
    enabled:  !!selectedId,
  });

  const events: CalEvent[] = calData ? buildEvents(calData) : [];

  const reschedule = useMutation({
    mutationFn: ({ id, start }: { id: string; start: Date }) =>
      apiClient.patch(`/posts/${id}`, { scheduled_at: start.toISOString() }),
    onSuccess: () => { toast.success("Post rescheduled"); refetch(); },
    onError:   () => toast.error("Reschedule failed"),
  });

  const handleEventDrop = useCallback(({ event, start }: { event: object; start: Date | string }) => {
    const e = event as CalEvent;
    reschedule.mutate({ id: e.id, start: new Date(start) });
  }, [reschedule]);

  const handleEventResize = useCallback(({ event, start }: { event: object; start: Date | string }) => {
    const e = event as CalEvent;
    reschedule.mutate({ id: e.id, start: new Date(start) });
  }, [reschedule]);

  return (
    <div className="space-y-4" style={{ height: "calc(100vh - 9rem)" }}>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Calendar</h2>
        <select
          className="rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          value={selectedId}
          onChange={(e) => { setSelectedId(e.target.value); setSelectedPost(null); }}
        >
          <option value="">— Select campaign —</option>
          {(campaigns ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        {selectedId && (
          <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setAddOpen(true)}>
            <Plus className="h-3.5 w-3.5" /> Add post
          </Button>
        )}

        <div className="flex flex-wrap gap-3 ml-auto text-xs">
          {Object.entries(PLATFORM_COLORS).map(([p, color]) => (
            <span key={p} className="flex items-center gap-1.5 text-muted-foreground">
              <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
              {p.replace("_", " ")}
            </span>
          ))}
        </div>
      </div>

      {loadingCampaigns ? (
        <Skeleton className="h-full rounded-lg" />
      ) : !selectedId ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed text-center">
          <CalendarDays className="h-10 w-10 text-muted-foreground opacity-40" />
          <div>
            <p className="text-sm font-medium">Select a campaign</p>
            <p className="text-xs text-muted-foreground mt-1">Choose a campaign above to view its scheduled posts.</p>
          </div>
        </div>
      ) : loadingCal ? (
        <Skeleton className="h-full rounded-lg" />
      ) : (
        <div className="rounded-lg border bg-card p-3 h-full">
          <DnDCalendar
            localizer={localizer}
            events={events}
            defaultView={Views.MONTH}
            views={[Views.MONTH, Views.WEEK, Views.AGENDA]}
            date={calDate}
            onNavigate={(date) => setCalDate(date)}
            onSelectEvent={(e: object) => setSelectedPost((e as CalEvent).post)}
            onEventDrop={handleEventDrop as any}
            onEventResize={handleEventResize as any}
            resizable
            eventPropGetter={(e: object) => ({
              style: {
                backgroundColor: PLATFORM_COLORS[(e as CalEvent).platform] ?? "#64748b",
                border: "none", borderRadius: "4px", color: "#fff",
                fontSize: "11px", padding: "2px 5px", cursor: "grab",
              },
            })}
            style={{ height: "100%" }}
          />
        </div>
      )}

      {selectedPost && (
        <PostModal
          post={selectedPost} open={!!selectedPost}
          onClose={() => setSelectedPost(null)}
          onSaved={(updated) => { setSelectedPost((p) => p ? { ...p, ...updated } : p); refetch(); }}
        />
      )}

      <AddPostModal
        open={addOpen} campaignId={selectedId}
        onClose={() => setAddOpen(false)}
        onAdded={() => refetch()}
      />
    </div>
  );
}
