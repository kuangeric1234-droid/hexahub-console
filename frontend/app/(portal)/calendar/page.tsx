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

// ── Post detail modal (Notion-style) ─────────────────────────────────────────

function PostModal({ post, open, onClose, onSaved }: {
  post: PostSlot; open: boolean; onClose: () => void; onSaved: (u: Partial<PostSlot>) => void;
}) {
  const [copy,        setCopy]        = useState(post.copy ?? "");
  const [note,        setNote]        = useState((post.metadata_json?.personal_note as string) ?? "");
  const [imageUrl,    setImageUrl]    = useState(post.visual_url ?? "");
  const [aiPrompt,    setAiPrompt]    = useState("");
  const [savingCopy,  setSavingCopy]  = useState(false);
  const [savingNote,  setSavingNote]  = useState(false);
  const [rewriting,   setRewriting]   = useState(false);
  const [uploading,   setUploading]   = useState(false);
  const [dragOver,    setDragOver]    = useState(false);

  const token = typeof window !== "undefined"
    ? (localStorage.getItem("hexa_token") ?? localStorage.getItem("hexa_portal_token"))
    : null;

  async function handleSaveCopy() {
    setSavingCopy(true);
    try { await apiClient.patch(`/posts/${post.id}`, { copy }); toast.success("Saved"); onSaved({ copy }); }
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

  async function handleImageUpload(file: File) {
    const allowed = ["image/jpeg", "image/png", "image/gif", "image/webp"];
    if (!allowed.includes(file.type)) { toast.error("Use JPEG, PNG, GIF or WebP"); return; }
    setUploading(true);
    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${BASE}/posts/${post.id}/upload-image`, {
        method: "POST",
        headers: {
          "ngrok-skip-browser-warning": "true",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: form,
      });
      if (!res.ok) throw new Error(await res.text());
      const data: { visual_url: string } = await res.json();
      setImageUrl(data.visual_url);
      onSaved({ visual_url: data.visual_url });
      toast.success("Image uploaded");
    } catch { toast.error("Upload failed"); }
    finally { setUploading(false); }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto p-0">
        {/* Notion-style header */}
        <div className="px-8 pt-8 pb-4 border-b">
          <div className="flex items-center gap-2 mb-3">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: PLATFORM_COLORS[post.platform] ?? "#64748b" }} />
            <span className="text-sm font-medium capitalize text-muted-foreground">{post.platform.replace("_", " ")}</span>
            <Badge variant={post.approval_status === "approved" ? "default" : post.approval_status === "rejected" ? "destructive" : "secondary"} className="text-xs">
              {post.approval_status}
            </Badge>
            <button onClick={onClose} className="ml-auto text-muted-foreground hover:text-foreground transition-colors">✕</button>
          </div>
          {post.scheduled_at && (
            <p className="text-xs text-muted-foreground flex items-center gap-1.5">
              📅 {fmt(new Date(post.scheduled_at), "EEEE, MMMM d yyyy 'at' h:mm a")}
            </p>
          )}
        </div>

        <div className="px-8 py-6 space-y-8">

          {/* ── Image upload ── */}
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Image</p>
            {imageUrl ? (
              <div className="relative group">
                <img src={imageUrl} alt="Post visual" className="w-full max-h-64 object-cover rounded-lg border" />
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-3">
                  <label className="cursor-pointer bg-white text-black text-xs font-medium px-3 py-1.5 rounded-md">
                    Replace
                    <input type="file" accept="image/*" className="hidden"
                      onChange={(e) => e.target.files?.[0] && handleImageUpload(e.target.files[0])} />
                  </label>
                  <button onClick={() => { setImageUrl(""); apiClient.patch(`/posts/${post.id}`, { visual_url: null } as any); }}
                    className="bg-white text-black text-xs font-medium px-3 py-1.5 rounded-md">
                    Remove
                  </button>
                </div>
              </div>
            ) : (
              <label
                className={`flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-8 cursor-pointer transition-colors ${dragOver ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) handleImageUpload(f); }}
              >
                <input type="file" accept="image/*" className="hidden"
                  onChange={(e) => e.target.files?.[0] && handleImageUpload(e.target.files[0])} />
                {uploading ? (
                  <><Loader2 className="h-6 w-6 animate-spin text-muted-foreground mb-2" /><p className="text-sm text-muted-foreground">Uploading…</p></>
                ) : (
                  <><div className="text-2xl mb-2">🖼️</div><p className="text-sm text-muted-foreground">Drop image here or click to upload</p><p className="text-xs text-muted-foreground mt-1">JPEG, PNG, GIF, WebP</p></>
                )}
              </label>
            )}
          </div>

          {/* ── Copy ── */}
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Post copy</p>
            <Textarea
              rows={10}
              value={copy}
              onChange={(e) => setCopy(e.target.value)}
              className="text-sm leading-relaxed resize-y border-0 bg-muted/30 focus-visible:ring-1 rounded-lg p-4"
              placeholder="Start writing your post…"
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">{copy.length} chars</span>
              <Button size="sm" onClick={handleSaveCopy} disabled={savingCopy} className="gap-1.5">
                {savingCopy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save
              </Button>
            </div>
          </div>

          {/* ── AI rewrite ── */}
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
              <Wand2 className="h-3.5 w-3.5" /> Modify with AI
            </p>
            <div className="flex gap-2">
              <Input value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="e.g. Add 3 hashtags, make it shorter, add a CTA…"
                className="text-sm"
                onKeyDown={(e) => { if (e.key === "Enter") handleAiRewrite(); }} />
              <Button size="sm" onClick={handleAiRewrite} disabled={rewriting || !aiPrompt.trim()}>
                {rewriting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Rewrite"}
              </Button>
            </div>
          </div>

          {/* ── Personal notes ── */}
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
              <MessageSquare className="h-3.5 w-3.5" /> Notes
            </p>
            <Textarea
              rows={4}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Private notes — only visible to you…"
              className="text-sm leading-relaxed resize-y border-0 bg-muted/30 focus-visible:ring-1 rounded-lg p-4"
            />
            <div className="flex justify-end">
              <Button size="sm" variant="outline" onClick={handleSaveNote} disabled={savingNote} className="gap-1.5">
                {savingNote ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save note
              </Button>
            </div>
          </div>

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

const ALL_POSTS = "__all__";

const APPROVAL_DOT: Record<string, string> = {
  approved:  "#22c55e",
  rejected:  "#ef4444",
  pending:   "#f59e0b",
};

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const [selectedId,   setSelectedId]   = useState<string>(ALL_POSTS);
  const [selectedPost, setSelectedPost] = useState<PostSlot | null>(null);
  const [addOpen,      setAddOpen]      = useState(false);
  const [calDate,      setCalDate]      = useState(new Date());

  const { data: campaigns, isLoading: loadingCampaigns } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn:  async () => (await api.get<Campaign[]>("/campaigns")).data,
  });

  const isAll = selectedId === ALL_POSTS;

  // All posts across every campaign
  const { data: allPosts, isLoading: loadingAll, error: allPostsError, refetch: refetchAll } = useQuery<PostSlot[]>({
    queryKey: ["posts", "all"],
    queryFn:  () => apiClient.get<PostSlot[]>("/posts?page_size=200"),
    enabled:  isAll,
    staleTime: 0,
  });

  // Single campaign calendar
  const { data: calData, isLoading: loadingCal, refetch: refetchCal } = useQuery<CampaignCalendar>({
    queryKey: ["calendar", selectedId],
    queryFn:  async () => (await api.get<CampaignCalendar>(`/campaigns/${selectedId}/calendar`)).data,
    enabled:  !isAll && !!selectedId,
  });

  const refetch = isAll ? refetchAll : refetchCal;

  const events: CalEvent[] = isAll
    ? (allPosts ?? [])
        .filter((p): p is PostSlot & { scheduled_at: string } => !!p.scheduled_at)
        .map((p) => {
          const start = new Date(p.scheduled_at);
          return {
            id: p.id,
            title: `${p.platform.replace("_", " ")} — ${p.copy ? p.copy.slice(0, 30) + "…" : "Draft"}`,
            start, end: new Date(start.getTime() + 30 * 60_000),
            platform: p.platform, post: p,
          };
        })
    : calData ? buildEvents(calData) : [];

  function getEventStyle(e: CalEvent) {
    const dotColor = APPROVAL_DOT[e.post.approval_status] ?? "#94a3b8";
    return {
      backgroundColor: PLATFORM_COLORS[e.platform] ?? "#64748b",
      border: `2px solid ${dotColor}`,
      borderRadius: "4px",
      color: "#fff",
      fontSize: "11px",
      padding: "2px 5px",
      cursor: "grab",
      opacity: e.post.approval_status === "pending" ? 0.75 : 1,
    };
  }

  const isLoading = isAll ? loadingAll : (loadingCampaigns || loadingCal);

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
          <option value={ALL_POSTS}>All posts (all campaigns)</option>
          <option disabled>─────────────</option>
          {(campaigns ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        {!isAll && selectedId && (
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
          <span className="w-px h-4 bg-border mx-1" />
          {Object.entries(APPROVAL_DOT).map(([status, color]) => (
            <span key={status} className="flex items-center gap-1.5 text-muted-foreground">
              <span className="h-2.5 w-2.5 rounded-sm border-2 shrink-0" style={{ borderColor: color }} />
              {status}
            </span>
          ))}
        </div>
      </div>

      {allPostsError && isAll && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load posts: {(allPostsError as Error).message}
        </div>
      )}

      {isLoading ? (
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
            eventPropGetter={(e: object) => ({ style: getEventStyle(e as CalEvent) })}
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
