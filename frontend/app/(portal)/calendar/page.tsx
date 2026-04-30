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
import { CalendarDays, Plus, Save, Wand2, Loader2, MessageSquare, Sparkles, ImageOff, FolderOpen, ChevronLeft, CheckCircle2 } from "lucide-react";
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
  id:           string;
  title:        string;
  start:        Date;
  end:          Date;
  platform:     string;
  post:         PostSlot;
  campaignName?: string;
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

// ── Generate Image Dialog ─────────────────────────────────────────────────────

interface DriveFile {
  id: string; name: string; mimeType: string;
  size: number | null; is_folder: boolean; thumbnail_url: string | null;
}
interface DriveFilesResponse {
  files: DriveFile[]; next_page_token: string | null;
}

function GenerateImageDialog({ open, onClose, platform, onUseImage }: {
  open: boolean; onClose: () => void;
  platform: string; onUseImage: (url: string) => void;
}) {
  const [folderStack,   setFolderStack]   = useState<{ id: string; name: string }[]>([]);
  const [selectedFile,  setSelectedFile]  = useState<DriveFile | null>(null);
  const [instructions,  setInstructions]  = useState("");
  const [generating,    setGenerating]    = useState(false);
  const [generatedUrl,  setGeneratedUrl]  = useState<string | null>(null);
  const [promptUsed,    setPromptUsed]    = useState("");

  const currentFolderId = folderStack.length > 0 ? folderStack[folderStack.length - 1].id : null;

  const { data: driveData, isLoading: driveLoading } = useQuery<DriveFilesResponse>({
    queryKey: ["drive-picker", currentFolderId],
    queryFn: () => {
      const params = new URLSearchParams({ page_size: "30", type: "image" });
      if (currentFolderId) params.set("folder_id", currentFolderId);
      return apiClient.get<DriveFilesResponse>(`/drive/files?${params}`);
    },
    staleTime: 60_000,
  });

  async function handleGenerate() {
    if (!instructions.trim() && !selectedFile) {
      toast.error("Add instructions or pick a reference image"); return;
    }
    setGenerating(true);
    setGeneratedUrl(null);
    try {
      const result = await apiClient.post<{ image_url: string; prompt_used: string }>(
        "/create/generate-image",
        { instructions, platform, drive_file_id: selectedFile?.id ?? null }
      );
      setGeneratedUrl(result.image_url);
      setPromptUsed(result.prompt_used);
    } catch (e: any) {
      toast.error(e.message ?? "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  function handleUse() {
    if (generatedUrl) { onUseImage(generatedUrl); onClose(); }
  }

  function reset() {
    setGeneratedUrl(null); setSelectedFile(null);
    setInstructions(""); setFolderStack([]);
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) { reset(); onClose(); } }}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden p-0 flex flex-col">
        <DialogHeader className="px-6 pt-5 pb-3 border-b flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-500" /> Generate Image with AI
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-1 overflow-hidden">
          {/* Left — Drive picker */}
          <div className="w-64 border-r flex-shrink-0 flex flex-col">
            <div className="px-4 py-3 border-b">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">Reference image</p>
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                {folderStack.length > 0 && (
                  <button onClick={() => setFolderStack((s) => s.slice(0, -1))}
                    className="hover:text-foreground"><ChevronLeft className="h-3 w-3" /></button>
                )}
                <span className="truncate">{folderStack.length > 0 ? folderStack[folderStack.length - 1].name : "Drive root"}</span>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {driveLoading ? (
                <div className="grid grid-cols-3 gap-1.5">
                  {[...Array(9)].map((_, i) => <div key={i} className="aspect-square rounded bg-muted animate-pulse" />)}
                </div>
              ) : !driveData?.files.length ? (
                <div className="text-center py-8 text-xs text-muted-foreground">No images found</div>
              ) : (
                <div className="grid grid-cols-3 gap-1.5">
                  {driveData.files.map((f) => f.is_folder ? (
                    <button key={f.id} onClick={() => setFolderStack((s) => [...s, { id: f.id, name: f.name }])}
                      className="aspect-square rounded border bg-muted/40 flex flex-col items-center justify-center gap-1 hover:bg-muted transition-colors p-1">
                      <FolderOpen className="h-4 w-4 text-amber-500" />
                      <span className="text-xs line-clamp-1 leading-tight">{f.name}</span>
                    </button>
                  ) : (
                    <button key={f.id} onClick={() => setSelectedFile(f === selectedFile ? null : f)}
                      className={`relative aspect-square rounded border overflow-hidden transition-all ${selectedFile?.id === f.id ? "ring-2 ring-purple-500 border-purple-500" : "hover:border-muted-foreground"}`}>
                      {f.thumbnail_url ? (
                        <img src={f.thumbnail_url} alt={f.name} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full bg-muted flex items-center justify-center">
                          <ImageOff className="h-4 w-4 text-muted-foreground" />
                        </div>
                      )}
                      {selectedFile?.id === f.id && (
                        <div className="absolute inset-0 bg-purple-500/20 flex items-center justify-center">
                          <CheckCircle2 className="h-5 w-5 text-purple-600" />
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {selectedFile && (
              <div className="px-3 py-2 border-t bg-muted/20 text-xs text-muted-foreground truncate">
                ✓ {selectedFile.name}
              </div>
            )}
          </div>

          {/* Right — instructions + preview */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Instructions</p>
                <Textarea
                  rows={4}
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="e.g. Warmer tones, show people at work, add dramatic lighting, urban Melbourne vibe, clean modern warehouse…"
                  className="text-sm resize-none border-0 bg-muted/30 focus-visible:ring-1 rounded-lg p-4"
                />
                <p className="text-xs text-muted-foreground">
                  {selectedFile ? "GPT-4 will analyse your reference image + apply these instructions." : "No reference — DALL-E generates from instructions only."}
                </p>
              </div>

              {!generatedUrl ? (
                <Button className="w-full gap-2 bg-purple-600 hover:bg-purple-700" onClick={handleGenerate}
                  disabled={generating || (!instructions.trim() && !selectedFile)}>
                  {generating
                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
                    : <><Sparkles className="h-4 w-4" /> Generate</>}
                </Button>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Preview</p>
                  <img src={generatedUrl} alt="Generated" className="w-full rounded-lg border" />
                  <div className="flex gap-2">
                    <Button className="flex-1" onClick={handleUse}>Use this image</Button>
                    <Button variant="outline" className="flex-1" onClick={() => { setGeneratedUrl(null); handleGenerate(); }}
                      disabled={generating}>
                      {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Try again"}
                    </Button>
                  </div>
                  {promptUsed && (
                    <details className="text-xs text-muted-foreground">
                      <summary className="cursor-pointer hover:text-foreground">View prompt used</summary>
                      <p className="mt-1 leading-relaxed">{promptUsed}</p>
                    </details>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ── Platform connection config ────────────────────────────────────────────────

const PLATFORM_META = ["instagram", "facebook"];

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
  if (platform === "blog")     return { connected: false, label: "WordPress" };
  return { connected: false, label: "Manual" };
}

// ── Post detail modal ─────────────────────────────────────────────────────────

function PostModal({ post, open, onClose, onSaved }: {
  post: PostSlot; open: boolean; onClose: () => void; onSaved: (u: Partial<PostSlot>) => void;
}) {
  const toLocalDatetime = (iso: string | null) =>
    iso ? fmt(new Date(iso), "yyyy-MM-dd'T'HH:mm") : "";

  const [copy,        setCopy]        = useState(post.copy ?? "");
  const [note,        setNote]        = useState((post.metadata_json?.personal_note as string) ?? "");
  const [imageUrl,    setImageUrl]    = useState(post.visual_url ?? "");
  const [aiPrompt,    setAiPrompt]    = useState("");
  const [scheduledAt, setScheduledAt] = useState(toLocalDatetime(post.scheduled_at));
  const [savingCopy,  setSavingCopy]  = useState(false);
  const [savingNote,  setSavingNote]  = useState(false);
  const [rewriting,   setRewriting]   = useState(false);
  const [uploading,   setUploading]   = useState(false);
  const [scheduling,   setScheduling]  = useState(false);
  const [approving,    setApproving]   = useState(false);
  const [rejectNote,   setRejectNote]  = useState("");
  const [dragOver,     setDragOver]    = useState(false);
  const [genImgOpen,   setGenImgOpen]  = useState(false);

  const token = typeof window !== "undefined"
    ? (localStorage.getItem("hexa_token") ?? localStorage.getItem("hexa_portal_token"))
    : null;

  const { data: metaStatus } = useQuery<{ connected: boolean; page_name?: string | null; ig_username?: string | null }>({
    queryKey: ["meta-status"],
    queryFn:  () => apiClient.get("/social/meta/status"),
    staleTime: 60_000,
  });

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

  async function handleSchedule() {
    if (!scheduledAt) { toast.error("Pick a date and time first"); return; }
    setScheduling(true);
    try {
      const iso = new Date(scheduledAt).toISOString();
      await apiClient.patch(`/posts/${post.id}`, { scheduled_at: iso, status: "scheduled" });
      toast.success("Post scheduled");
      onSaved({ scheduled_at: iso, status: "scheduled" });
    } catch { toast.error("Scheduling failed"); }
    finally { setScheduling(false); }
  }

  async function handlePublishNow() {
    setScheduling(true);
    try {
      const iso = new Date().toISOString();
      await apiClient.patch(`/posts/${post.id}`, { scheduled_at: iso, status: "scheduled" });
      toast.success("Queued for immediate publish — fires within 1 minute");
      onSaved({ scheduled_at: iso, status: "scheduled" });
    } catch { toast.error("Failed"); }
    finally { setScheduling(false); }
  }

  async function handleApprove() {
    setApproving(true);
    try {
      await apiClient.post(`/posts/${post.id}/approve`, {});
      toast.success("Post approved");
      onSaved({ approval_status: "approved" });
    } catch { toast.error("Failed to approve"); }
    finally { setApproving(false); }
  }

  async function handleReject() {
    setApproving(true);
    try {
      await apiClient.post(`/posts/${post.id}/reject`, { feedback: rejectNote || "Rejected from calendar" });
      toast.success("Post rejected");
      onSaved({ approval_status: "rejected" });
      setRejectNote("");
    } catch { toast.error("Failed to reject"); }
    finally { setApproving(false); }
  }

  async function handleUnschedule() {
    setScheduling(true);
    try {
      await apiClient.patch(`/posts/${post.id}`, { status: "approved" });
      toast.success("Unscheduled");
      onSaved({ status: "approved" });
    } catch { toast.error("Failed"); }
    finally { setScheduling(false); }
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

  const { connected: platformConnected, label: platformLabel } =
    platformConnectionLabel(post.platform, metaStatus);

  const isScheduled = post.status === "scheduled";
  const canSchedule = post.approval_status === "approved";

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden p-0 flex flex-col">

        {/* Header */}
        <div className="px-8 pt-6 pb-4 border-b flex-shrink-0">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: PLATFORM_COLORS[post.platform] ?? "#64748b" }} />
            <span className="text-sm font-medium capitalize text-muted-foreground">{post.platform.replace("_", " ")}</span>
            <Badge variant={post.approval_status === "approved" ? "default" : post.approval_status === "rejected" ? "destructive" : "secondary"} className="text-xs">
              {post.approval_status}
            </Badge>
            {isScheduled && <Badge className="text-xs bg-blue-500 hover:bg-blue-500">scheduled</Badge>}
            {(post as any).campaignName && (
              <span className="text-xs text-muted-foreground ml-1">📁 {(post as any).campaignName}</span>
            )}
            <button onClick={onClose} className="ml-auto text-muted-foreground hover:text-foreground transition-colors">✕</button>
          </div>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">

          {/* Left — content */}
          <div className="flex-1 overflow-y-auto px-8 py-6 space-y-8">

            {/* Image upload */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Image</p>
                <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5 border-purple-200 text-purple-700 hover:bg-purple-50"
                  onClick={() => setGenImgOpen(true)}>
                  <Sparkles className="h-3 w-3" /> Generate with AI
                </Button>
              </div>
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
                    : <><div className="text-2xl mb-2">🖼️</div><p className="text-sm text-muted-foreground">Drop image here or click to upload</p><p className="text-xs text-muted-foreground mt-1">JPEG, PNG, GIF, WebP</p></>}
                </label>
              )}
            </div>

            {/* Copy */}
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Post copy</p>
              <Textarea rows={10} value={copy} onChange={(e) => setCopy(e.target.value)}
                className="text-sm leading-relaxed resize-y border-0 bg-muted/30 focus-visible:ring-1 rounded-lg p-4"
                placeholder="Start writing your post…" />
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
                  placeholder="e.g. Add 3 hashtags, make it shorter, add a CTA…" className="text-sm"
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
              <Textarea rows={4} value={note} onChange={(e) => setNote(e.target.value)}
                placeholder="Private notes — only visible to you…"
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

            {/* Approval */}
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Approval</p>
              {post.approval_status === "approved" ? (
                <div className="flex items-center gap-2 text-green-600 text-sm font-medium">
                  <span>✓</span><span>Approved</span>
                </div>
              ) : post.approval_status === "rejected" ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-destructive text-sm font-medium">
                    <span>✗</span><span>Rejected</span>
                  </div>
                  <Button size="sm" className="w-full gap-1.5 bg-green-600 hover:bg-green-700"
                    onClick={handleApprove} disabled={approving}>
                    {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Re-approve"}
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  <Button size="sm" className="w-full bg-green-600 hover:bg-green-700"
                    onClick={handleApprove} disabled={approving}>
                    {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "✓ Approve"}
                  </Button>
                  <Input
                    value={rejectNote}
                    onChange={(e) => setRejectNote(e.target.value)}
                    placeholder="Rejection reason (optional)"
                    className="text-xs"
                  />
                  <Button size="sm" variant="outline" className="w-full text-destructive border-destructive/30"
                    onClick={handleReject} disabled={approving}>
                    ✗ Reject
                  </Button>
                </div>
              )}
            </div>

            <Separator />

            {/* Posting on */}
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Posting on</p>
              <Input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="text-xs"
              />
            </div>

            <Separator />

            {/* Posting to */}
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Posting to</p>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: PLATFORM_COLORS[post.platform] ?? "#64748b" }} />
                  <span className="text-sm capitalize">{post.platform.replace("_", " ")}</span>
                </div>
                <span className={`text-xs font-medium ${platformConnected ? "text-green-600" : "text-muted-foreground"}`}>
                  {platformConnected ? "✓" : "✗"}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{platformLabel}</p>
              {!platformConnected && PLATFORM_META.includes(post.platform) && (
                <p className="text-xs text-amber-600">Connect via Settings → Social Accounts</p>
              )}
            </div>

            <Separator />

            {/* Actions */}
            <div className="space-y-2">
              {!canSchedule && (
                <p className="text-xs text-muted-foreground text-center pb-1">Post must be approved before scheduling</p>
              )}
              <Button
                className="w-full gap-1.5" size="sm"
                onClick={handleSchedule}
                disabled={scheduling || !scheduledAt || !canSchedule}
              >
                {scheduling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CalendarDays className="h-3.5 w-3.5" />}
                {isScheduled ? "Reschedule" : "Schedule"}
              </Button>
              <Button
                variant="outline" className="w-full" size="sm"
                onClick={handlePublishNow}
                disabled={scheduling || !canSchedule}
              >
                Publish now
              </Button>
              {isScheduled && (
                <Button variant="ghost" className="w-full text-muted-foreground text-xs" size="sm"
                  onClick={handleUnschedule} disabled={scheduling}>
                  Unschedule
                </Button>
              )}
            </div>

          </div>
        </div>
      </DialogContent>

      <GenerateImageDialog
        open={genImgOpen}
        onClose={() => setGenImgOpen(false)}
        platform={post.platform}
        onUseImage={(url) => {
          setImageUrl(url);
          apiClient.patch(`/posts/${post.id}`, { visual_url: url });
          onSaved({ visual_url: url });
          toast.success("Generated image attached to post");
        }}
      />
    </Dialog>
  );
}

// ── Add post modal ────────────────────────────────────────────────────────────

function AddPostModal({ open, campaignId, campaigns, onClose, onAdded }: {
  open: boolean; campaignId: string; campaigns: Campaign[]; onClose: () => void; onAdded: () => void;
}) {
  const [platform,       setPlatform]       = useState("linkedin");
  const [scheduledAt,    setScheduledAt]    = useState("");
  const [copy,           setCopy]           = useState("");
  const [aiPrompt,       setAiPrompt]       = useState("");
  const [selectedCampaign, setSelectedCampaign] = useState(campaignId);
  const [generating,     setGenerating]     = useState(false);
  const [saving,         setSaving]         = useState(false);

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
    if (!copy.trim()) { toast.error("Add some copy first"); return; }
    setSaving(true);
    try {
      await apiClient.post("/posts", {
        ...(selectedCampaign ? { campaign_id: selectedCampaign } : {}),
        platform, copy, status: "draft",
        ...(scheduledAt ? { scheduled_at: new Date(scheduledAt).toISOString() } : {}),
      });
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
              <Label>Scheduled date & time <span className="text-muted-foreground font-normal">(optional)</span></Label>
              <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Campaign <span className="text-muted-foreground font-normal">(optional)</span></Label>
            <select className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={selectedCampaign} onChange={(e) => setSelectedCampaign(e.target.value)}>
              <option value="">— No campaign (standalone) —</option>
              {campaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
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

const APPROVAL_FILTERS = [
  { value: "all",      label: "All statuses" },
  { value: "pending",  label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

export default function CalendarPage() {
  const [selectedId,      setSelectedId]      = useState<string>(ALL_POSTS);
  const [selectedPost,    setSelectedPost]    = useState<PostSlot | null>(null);
  const [addOpen,         setAddOpen]         = useState(false);
  const [calDate,         setCalDate]         = useState(new Date());
  const [approvalFilter,  setApprovalFilter]  = useState("all");

  const { data: campaigns, isLoading: loadingCampaigns } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn:  async () => (await api.get<Campaign[]>("/campaigns")).data,
  });

  const isAll = selectedId === ALL_POSTS;

  // All posts across every campaign
  const { data: allPosts, isLoading: loadingAll, error: allPostsError, refetch: refetchAll } = useQuery<PostSlot[]>({
    queryKey: ["posts", "all"],
    queryFn:  () => apiClient.get<PostSlot[]>("/posts?page_size=100"),
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

  const campaignMap = Object.fromEntries((campaigns ?? []).map(c => [c.id, c.name]));

  const rawEvents: CalEvent[] = isAll
    ? (allPosts ?? [])
        .filter((p): p is PostSlot & { scheduled_at: string } => !!p.scheduled_at)
        .map((p) => {
          const start = new Date(p.scheduled_at);
          const campaignName = p.campaign_id ? campaignMap[p.campaign_id] : undefined;
          return {
            id: p.id,
            title: `${p.platform.replace("_", " ")} — ${p.copy ? p.copy.slice(0, 30) + "…" : "Draft"}`,
            start, end: new Date(start.getTime() + 30 * 60_000),
            platform: p.platform, post: p, campaignName,
          };
        })
    : calData ? buildEvents(calData) : [];

  const events = approvalFilter === "all"
    ? rawEvents
    : rawEvents.filter((e) => e.post.approval_status === approvalFilter);

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

        <select
          className="rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          value={approvalFilter}
          onChange={(e) => setApprovalFilter(e.target.value)}
        >
          {APPROVAL_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>

        <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setAddOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> Add post
        </Button>

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
            popup
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
        open={addOpen}
        campaignId={isAll ? "" : selectedId}
        campaigns={campaigns ?? []}
        onClose={() => setAddOpen(false)}
        onAdded={() => refetch()}
      />
    </div>
  );
}
