"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format, isToday, isTomorrow, isPast } from "date-fns";
import { CalendarDays, Clock, Loader2, ImageOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api";
import { PostSlot } from "@/lib/types";
import { toast } from "sonner";
import { Save, Wand2, MessageSquare } from "lucide-react";

const PLATFORM_COLORS: Record<string, string> = {
  linkedin:       "#0077b5",
  instagram:      "#e1306c",
  facebook:       "#1877f2",
  blog:           "#6366f1",
  xiaohongshu:    "#ff2442",
  wechat_moments: "#07c160",
};

const PLATFORM_ICONS: Record<string, string> = {
  linkedin:       "in",
  instagram:      "IG",
  facebook:       "FB",
  blog:           "✍",
  xiaohongshu:    "小",
  wechat_moments: "微",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function dayLabel(date: Date): string {
  if (isToday(date))    return "Today";
  if (isTomorrow(date)) return "Tomorrow";
  return format(date, "EEEE, MMMM d");
}

function groupByDay(posts: PostSlot[]): Map<string, PostSlot[]> {
  const map = new Map<string, PostSlot[]>();
  const sorted = [...posts].sort((a, b) =>
    new Date(a.scheduled_at!).getTime() - new Date(b.scheduled_at!).getTime()
  );
  for (const post of sorted) {
    const key = format(new Date(post.scheduled_at!), "yyyy-MM-dd");
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(post);
  }
  return map;
}

function platformConnectionLabel(
  platform: string,
  metaStatus: { connected: boolean; page_name?: string | null; ig_username?: string | null } | undefined,
): { connected: boolean; label: string } {
  if (platform === "instagram") {
    const ok = !!metaStatus?.connected && !!metaStatus?.ig_username;
    return { connected: ok, label: ok ? `@${metaStatus!.ig_username}` : "Not connected" };
  }
  if (platform === "facebook") {
    const ok = !!metaStatus?.connected && !!metaStatus?.page_name;
    return { connected: ok, label: ok ? metaStatus!.page_name! : "Not connected" };
  }
  if (platform === "linkedin") return { connected: false, label: "Not configured" };
  return { connected: false, label: "Manual" };
}

// ── Post card ─────────────────────────────────────────────────────────────────

function PostCard({ post, onClick }: { post: PostSlot; onClick: () => void }) {
  const date        = new Date(post.scheduled_at!);
  const overdue     = isPast(date) && post.status === "scheduled";
  const platformColor = PLATFORM_COLORS[post.platform] ?? "#64748b";
  const icon          = PLATFORM_ICONS[post.platform] ?? "?";

  return (
    <button
      onClick={onClick}
      className="w-full text-left flex items-start gap-4 p-4 rounded-xl border bg-card hover:bg-muted/40 transition-colors group"
    >
      {/* Platform dot */}
      <div
        className="h-9 w-9 rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5"
        style={{ backgroundColor: platformColor }}
      >
        {icon}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium capitalize text-muted-foreground">
            {post.platform.replace("_", " ")}
          </span>
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {format(date, "h:mm a")}
          </span>
          {overdue && (
            <Badge variant="destructive" className="text-xs py-0">overdue</Badge>
          )}
        </div>
        <p className="text-sm text-foreground line-clamp-2 leading-relaxed">
          {post.copy ?? <span className="text-muted-foreground italic">No copy yet</span>}
        </p>
      </div>

      {/* Thumbnail */}
      {post.visual_url ? (
        <img
          src={post.visual_url}
          alt=""
          className="h-14 w-14 rounded-lg object-cover flex-shrink-0 border"
        />
      ) : (
        <div className="h-14 w-14 rounded-lg border bg-muted flex items-center justify-center flex-shrink-0">
          <ImageOff className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
    </button>
  );
}

// ── Post modal (scheduling panel) ─────────────────────────────────────────────

function ScheduledPostModal({ post, open, onClose, onSaved }: {
  post: PostSlot; open: boolean; onClose: () => void; onSaved: (u: Partial<PostSlot>) => void;
}) {
  const toLocalDatetime = (iso: string | null) =>
    iso ? format(new Date(iso), "yyyy-MM-dd'T'HH:mm") : "";

  const [copy,        setCopy]        = useState(post.copy ?? "");
  const [note,        setNote]        = useState((post.metadata_json?.personal_note as string) ?? "");
  const [imageUrl,    setImageUrl]    = useState(post.visual_url ?? "");
  const [aiPrompt,    setAiPrompt]    = useState("");
  const [scheduledAt, setScheduledAt] = useState(toLocalDatetime(post.scheduled_at));
  const [savingCopy,  setSavingCopy]  = useState(false);
  const [savingNote,  setSavingNote]  = useState(false);
  const [rewriting,   setRewriting]   = useState(false);
  const [uploading,   setUploading]   = useState(false);
  const [scheduling,  setScheduling]  = useState(false);
  const [dragOver,    setDragOver]    = useState(false);

  const token = typeof window !== "undefined"
    ? (localStorage.getItem("hexa_token") ?? localStorage.getItem("hexa_portal_token"))
    : null;

  const { data: metaStatus } = useQuery<{ connected: boolean; page_name?: string | null; ig_username?: string | null }>({
    queryKey: ["meta-status"],
    queryFn:  () => apiClient.get("/social/meta/status"),
    staleTime: 60_000,
  });

  const { connected: platformConnected, label: platformLabel } =
    platformConnectionLabel(post.platform, metaStatus);

  const isScheduled = post.status === "scheduled";

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

  async function handleReschedule() {
    if (!scheduledAt) { toast.error("Pick a date and time first"); return; }
    setScheduling(true);
    try {
      const iso = new Date(scheduledAt).toISOString();
      await apiClient.patch(`/posts/${post.id}`, { scheduled_at: iso, status: "scheduled" });
      toast.success("Rescheduled");
      onSaved({ scheduled_at: iso, status: "scheduled" });
    } catch { toast.error("Failed"); }
    finally { setScheduling(false); }
  }

  async function handleUnschedule() {
    setScheduling(true);
    try {
      await apiClient.patch(`/posts/${post.id}`, { status: "approved" });
      toast.success("Unscheduled — moved back to approved");
      onSaved({ status: "approved" });
      onClose();
    } catch { toast.error("Failed"); }
    finally { setScheduling(false); }
  }

  async function handleImageUpload(file: File) {
    if (!["image/jpeg", "image/png", "image/gif", "image/webp"].includes(file.type)) {
      toast.error("Use JPEG, PNG, GIF or WebP"); return;
    }
    setUploading(true);
    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${BASE}/posts/${post.id}/upload-image`, {
        method: "POST",
        headers: { "ngrok-skip-browser-warning": "true", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
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
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden p-0 flex flex-col">

        {/* Header */}
        <div className="px-8 pt-6 pb-4 border-b flex-shrink-0">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: PLATFORM_COLORS[post.platform] ?? "#64748b" }} />
            <span className="text-sm font-medium capitalize text-muted-foreground">{post.platform.replace("_", " ")}</span>
            <Badge className="text-xs bg-blue-500 hover:bg-blue-500">scheduled</Badge>
            {post.scheduled_at && (
              <span className="text-xs text-muted-foreground">
                {format(new Date(post.scheduled_at), "EEE MMM d 'at' h:mm a")}
              </span>
            )}
            <button onClick={onClose} className="ml-auto text-muted-foreground hover:text-foreground">✕</button>
          </div>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">

          {/* Left */}
          <div className="flex-1 overflow-y-auto px-8 py-6 space-y-8">

            {/* Image */}
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Image</p>
              {imageUrl ? (
                <div className="relative group">
                  <img src={imageUrl} alt="" className="w-full max-h-64 object-cover rounded-lg border" />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-3">
                    <label className="cursor-pointer bg-white text-black text-xs font-medium px-3 py-1.5 rounded-md">
                      Replace
                      <input type="file" accept="image/*" className="hidden"
                        onChange={(e) => e.target.files?.[0] && handleImageUpload(e.target.files[0])} />
                    </label>
                    <button onClick={() => { setImageUrl(""); apiClient.patch(`/posts/${post.id}`, { visual_url: null } as any); }}
                      className="bg-white text-black text-xs font-medium px-3 py-1.5 rounded-md">Remove</button>
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
                  {uploading
                    ? <><Loader2 className="h-6 w-6 animate-spin text-muted-foreground mb-2" /><p className="text-sm text-muted-foreground">Uploading…</p></>
                    : <><div className="text-2xl mb-2">🖼️</div><p className="text-sm text-muted-foreground">Drop image here or click to upload</p></>}
                </label>
              )}
            </div>

            {/* Copy */}
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Post copy</p>
              <Textarea rows={10} value={copy} onChange={(e) => setCopy(e.target.value)}
                className="text-sm leading-relaxed resize-y border-0 bg-muted/30 focus-visible:ring-1 rounded-lg p-4" />
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{copy.length} chars</span>
                <Button size="sm" onClick={handleSaveCopy} disabled={savingCopy} className="gap-1.5">
                  {savingCopy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save
                </Button>
              </div>
            </div>

            {/* AI rewrite */}
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                <Wand2 className="h-3.5 w-3.5" /> Modify with AI
              </p>
              <div className="flex gap-2">
                <Input value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
                  placeholder="e.g. Make it shorter, add emojis, add a CTA…" className="text-sm"
                  onKeyDown={(e) => { if (e.key === "Enter") handleAiRewrite(); }} />
                <Button size="sm" onClick={handleAiRewrite} disabled={rewriting || !aiPrompt.trim()}>
                  {rewriting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Rewrite"}
                </Button>
              </div>
            </div>

            {/* Notes */}
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                <MessageSquare className="h-3.5 w-3.5" /> Notes
              </p>
              <Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)}
                placeholder="Private notes…"
                className="text-sm leading-relaxed resize-y border-0 bg-muted/30 focus-visible:ring-1 rounded-lg p-4" />
              <div className="flex justify-end">
                <Button size="sm" variant="outline" onClick={handleSaveNote} disabled={savingNote} className="gap-1.5">
                  {savingNote ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} Save note
                </Button>
              </div>
            </div>

          </div>

          {/* Right — scheduling panel */}
          <div className="w-64 border-l flex-shrink-0 bg-muted/10 overflow-y-auto p-5 space-y-6">

            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Posting on</p>
              <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} className="text-xs" />
            </div>

            <Separator />

            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Posting to</p>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: PLATFORM_COLORS[post.platform] ?? "#64748b" }} />
                  <span className="text-sm capitalize">{post.platform.replace("_", " ")}</span>
                </div>
                <span className={`text-xs font-medium ${platformConnected ? "text-green-600" : "text-muted-foreground"}`}>
                  {platformConnected ? "✓" : "✗"}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{platformLabel}</p>
            </div>

            <Separator />

            <div className="space-y-2">
              <Button className="w-full gap-1.5" size="sm" onClick={handleReschedule} disabled={scheduling || !scheduledAt}>
                {scheduling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CalendarDays className="h-3.5 w-3.5" />}
                Reschedule
              </Button>
              <Button variant="ghost" className="w-full text-muted-foreground text-xs" size="sm"
                onClick={handleUnschedule} disabled={scheduling}>
                Unschedule
              </Button>
            </div>

          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ScheduledPage() {
  const [selectedPost, setSelectedPost] = useState<PostSlot | null>(null);

  const { data: posts, isLoading, refetch } = useQuery<PostSlot[]>({
    queryKey: ["posts", "scheduled"],
    queryFn:  () => apiClient.get<PostSlot[]>("/posts?page_size=200"),
    select:   (all) => all.filter((p) => p.status === "scheduled" && p.scheduled_at),
    staleTime: 0,
  });

  const grouped = posts ? groupByDay(posts) : new Map();

  return (
    <div className="max-w-3xl mx-auto space-y-8 pb-12">

      {/* Header */}
      <div className="flex items-center gap-3">
        <CalendarDays className="h-5 w-5 text-muted-foreground" />
        <h2 className="text-lg font-semibold">Scheduled</h2>
        {posts && (
          <span className="text-sm text-muted-foreground">
            {posts.length} post{posts.length !== 1 ? "s" : ""} queued
          </span>
        )}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      )}

      {!isLoading && posts?.length === 0 && (
        <div className="text-center py-20 text-muted-foreground">
          <CalendarDays className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No posts scheduled yet.</p>
          <p className="text-xs mt-1">Approve a post on the Calendar and hit Schedule.</p>
        </div>
      )}

      {[...grouped.entries()].map(([dateKey, dayPosts]: [string, PostSlot[]]) => {
        const date = new Date(dateKey + "T00:00:00");
        return (
          <div key={dateKey} className="space-y-3">
            <div className="flex items-center gap-3">
              <p className="text-sm font-semibold">{dayLabel(date)}</p>
              <span className="text-xs text-muted-foreground">{format(date, "MMMM d, yyyy")}</span>
              <div className="flex-1 h-px bg-border" />
              <span className="text-xs text-muted-foreground">{dayPosts.length} post{dayPosts.length !== 1 ? "s" : ""}</span>
            </div>
            <div className="space-y-2">
              {dayPosts.map((post) => (
                <PostCard key={post.id} post={post} onClick={() => setSelectedPost(post)} />
              ))}
            </div>
          </div>
        );
      })}

      {selectedPost && (
        <ScheduledPostModal
          post={selectedPost}
          open={!!selectedPost}
          onClose={() => setSelectedPost(null)}
          onSaved={(updated) => {
            setSelectedPost((p) => p ? { ...p, ...updated } : p);
            refetch();
          }}
        />
      )}
    </div>
  );
}
