"use client";
import { useRef, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Loader2, Sparkles, Copy, Check, Upload, X, Image as ImageIcon,
  LayoutGrid, Film, FileText, Lightbulb, Wand2, CalendarDays, BookmarkPlus,
  History, RotateCcw, Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import { Campaign } from "@/lib/types";
import { toast } from "sonner";

export interface AgentFormConfig {
  title:            string;
  description:      string;
  platform:         string;
  briefLabel:       string;
  briefPlaceholder: string;
  badge?:           string;
}

interface FormatRecommendation {
  format:       string;
  rationale:    string;
  slides:       number | null;
  alternatives: string[];
}

interface ImageSuggestion {
  description: string;
  style:       string;
  mood:        string;
}

interface AssistResult {
  copy:                   string;
  format_recommendation:  FormatRecommendation;
  visual_brief:           string;
  image_suggestions:      ImageSuggestion[];
  char_count:             number;
  word_count:             number;
}

const FORMAT_ICONS: Record<string, React.ReactNode> = {
  carousel:     <LayoutGrid className="h-4 w-4" />,
  video:        <Film className="h-4 w-4" />,
  reel:         <Film className="h-4 w-4" />,
  single_image: <ImageIcon className="h-4 w-4" />,
  article:      <FileText className="h-4 w-4" />,
  document:     <FileText className="h-4 w-4" />,
  infographic:  <LayoutGrid className="h-4 w-4" />,
};

const FORMAT_LABELS: Record<string, string> = {
  single_image: "Single Image",
  carousel:     "Carousel",
  video:        "Video",
  reel:         "Reel",
  article:      "Article",
  document:     "Document",
  infographic:  "Infographic",
};

export function AgentForm({ config }: { config: AgentFormConfig }) {
  const platformKey = config.platform.toLowerCase().replace(" ", "_").replace("-", "_");

  const [brief,        setBrief]        = useState("");
  const [result,       setResult]       = useState<AssistResult | null>(null);
  const [loading,      setLoading]      = useState(false);
  const [copied,       setCopied]       = useState(false);
  const [imageFile,    setImageFile]    = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [dragOver,     setDragOver]     = useState(false);
  const fileInputRef   = useRef<HTMLInputElement>(null);

  // Save to campaign
  const [campaignId,   setCampaignId]   = useState("");
  const [scheduledAt,  setScheduledAt]  = useState("");
  const [saving,       setSaving]       = useState(false);
  const [saved,        setSaved]        = useState(false);

  const { data: campaigns } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn:  () => apiClient.get<Campaign[]>("/campaigns"),
    staleTime: 30_000,
  });

  // History
  const HISTORY_KEY = `create_history_${platformKey}`;
  type HistoryEntry = { id: string; ts: number; brief: string; headline: string; result: AssistResult };

  function loadHistory(): HistoryEntry[] {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]"); }
    catch { return []; }
  }

  const [history, setHistory] = useState<HistoryEntry[]>(() =>
    typeof window !== "undefined" ? loadHistory() : []
  );

  function saveToHistory(brief: string, res: AssistResult) {
    const headline = res.copy.split("\n").find(l => l.trim()) ?? brief.slice(0, 60);
    const entry: HistoryEntry = {
      id:       Math.random().toString(36).slice(2),
      ts:       Date.now(),
      brief,
      headline: headline.slice(0, 80),
      result:   res,
    };
    const updated = [entry, ...loadHistory()].slice(0, 30);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
    setHistory(updated);
  }

  function restoreFromHistory(entry: HistoryEntry) {
    setResult(entry.result);
    setBrief(entry.brief);
    setSaved(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function deleteHistoryItem(id: string) {
    const updated = history.filter(h => h.id !== id);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(updated));
    setHistory(updated);
  }

  function clearHistory() {
    localStorage.removeItem(HISTORY_KEY);
    setHistory([]);
  }

  function handleFileSelect(file: File) {
    if (!file.type.startsWith("image/")) {
      toast.error("Please upload an image file");
      return;
    }
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = (e) => setImagePreview(e.target?.result as string);
    reader.readAsDataURL(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  }

  function clearImage() {
    setImageFile(null);
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setResult(null);

    try {
      let image_base64: string | undefined;
      let image_mime_type: string | undefined;

      if (imageFile) {
        const ab = await imageFile.arrayBuffer();
        const bytes = new Uint8Array(ab);
        let binary = "";
        bytes.forEach((b) => { binary += String.fromCharCode(b); });
        image_base64   = btoa(binary);
        image_mime_type = imageFile.type;
      }

      const recentHistory = loadHistory().slice(0, 3).map(h => ({
        brief: h.brief,
        copy:  h.result.copy,
      }));

      const data = await apiClient.post<AssistResult>("/create/assisted", {
        platform:        platformKey,
        brief,
        image_base64,
        image_mime_type,
        history:         recentHistory,
      });

      setResult(data);
      setSaved(false);
      saveToHistory(brief, data);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(schedule: boolean) {
    if (!result || !campaignId) { toast.error("Select a campaign first"); return; }
    if (schedule && !scheduledAt) { toast.error("Pick a date and time"); return; }
    setSaving(true);
    try {
      await apiClient.post("/posts", {
        campaign_id:  campaignId,
        platform:     platformKey,
        copy:         result.copy,
        status:       "draft",
        ...(schedule ? { scheduled_at: new Date(scheduledAt).toISOString() } : {}),
      });
      setSaved(true);
      toast.success(schedule ? "Post saved and scheduled ✓" : "Post saved as draft ✓");
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  }

  function handleCopy() {
    if (!result) return;
    navigator.clipboard.writeText(result.copy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-4 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">{config.title}</h2>
            {config.badge && <Badge variant="secondary" className="text-xs">{config.badge}</Badge>}
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">{config.description}</p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* ── Left: Input ── */}
        <form onSubmit={handleGenerate} className="space-y-3">
          <Card>
            <CardContent className="pt-4 space-y-4">
              {/* Brief */}
              <div className="space-y-1.5">
                <Label>{config.briefLabel}</Label>
                <Textarea
                  rows={5}
                  placeholder={imageFile ? "Optional — leave blank to let the AI interpret the image…" : config.briefPlaceholder}
                  value={brief}
                  onChange={(e) => setBrief(e.target.value)}
                />
              </div>

              <Separator />

              {/* Image upload */}
              <div className="space-y-1.5">
                <Label className="flex items-center gap-1.5">
                  <ImageIcon className="h-3.5 w-3.5" />
                  Image <span className="text-muted-foreground font-normal">(optional)</span>
                </Label>

                {imagePreview ? (
                  <div className="relative rounded-lg overflow-hidden border">
                    <img src={imagePreview} alt="upload preview"
                      className="w-full h-40 object-cover" />
                    <button type="button"
                      onClick={clearImage}
                      className="absolute top-2 right-2 rounded-full bg-background/80 p-1 hover:bg-background border">
                      <X className="h-3.5 w-3.5" />
                    </button>
                    <div className="absolute bottom-0 inset-x-0 bg-background/80 text-xs px-2 py-1 text-muted-foreground truncate">
                      {imageFile?.name}
                    </div>
                  </div>
                ) : (
                  <div
                    className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                      dragOver ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
                    }`}
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="h-6 w-6 mx-auto mb-2 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Drop an image or <span className="text-primary underline">browse</span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">PNG, JPG, WebP</p>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => { if (e.target.files?.[0]) handleFileSelect(e.target.files[0]); }}
                />
              </div>

              <Button type="submit" className="w-full gap-2" disabled={loading || (!brief.trim() && !imageFile)}>
                {loading
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
                  : <><Sparkles className="h-4 w-4" /> Generate</>
                }
              </Button>
            </CardContent>
          </Card>
        </form>

        {/* ── Right: Output ── */}
        <div className="space-y-3">
          {loading ? (
            <Card className="min-h-[300px] flex items-center justify-center">
              <div className="flex flex-col items-center gap-3 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin" />
                <p className="text-sm">{imageFile ? "Analysing image and generating…" : "Generating content…"}</p>
              </div>
            </Card>
          ) : result ? (
            <div className="space-y-3">
              {/* Copy output */}
              <Card>
                <CardHeader className="pb-2 pt-3 px-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">Copy</CardTitle>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {result.char_count} chars · {result.word_count} words
                      </span>
                      <Button variant="ghost" size="sm" onClick={handleCopy} className="h-7 gap-1.5 text-xs">
                        {copied ? <><Check className="h-3 w-3" /> Copied</> : <><Copy className="h-3 w-3" /> Copy</>}
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  <pre className="text-sm whitespace-pre-wrap font-sans">{result.copy}</pre>
                </CardContent>
              </Card>

              {/* Format recommendation */}
              <Card>
                <CardHeader className="pb-2 pt-3 px-4">
                  <CardTitle className="text-sm flex items-center gap-1.5">
                    <Wand2 className="h-4 w-4 text-primary" />
                    Recommended Format
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="default" className="gap-1.5 capitalize">
                      {FORMAT_ICONS[result.format_recommendation.format]}
                      {FORMAT_LABELS[result.format_recommendation.format] ?? result.format_recommendation.format}
                      {result.format_recommendation.slides && ` · ${result.format_recommendation.slides} slides`}
                    </Badge>
                    {result.format_recommendation.alternatives.map((alt) => (
                      <Badge key={alt} variant="secondary" className="text-xs capitalize">
                        {FORMAT_LABELS[alt] ?? alt}
                      </Badge>
                    ))}
                  </div>
                  <p className="text-sm text-muted-foreground">{result.format_recommendation.rationale}</p>
                </CardContent>
              </Card>

              {/* Visual brief */}
              <Card>
                <CardHeader className="pb-2 pt-3 px-4">
                  <CardTitle className="text-sm flex items-center gap-1.5">
                    <ImageIcon className="h-4 w-4 text-primary" />
                    Visual Brief
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  <p className="text-sm text-muted-foreground">{result.visual_brief}</p>
                  <div className="flex gap-2 mt-3">
                    <Button size="sm" variant="outline" className="gap-1.5 text-xs" disabled>
                      <Wand2 className="h-3.5 w-3.5" />
                      Generate AI image
                      <Badge variant="secondary" className="text-[10px] ml-1">Soon</Badge>
                    </Button>
                    <Button size="sm" variant="outline" className="gap-1.5 text-xs"
                      onClick={() => fileInputRef.current?.click()}>
                      <Upload className="h-3.5 w-3.5" />
                      Upload image
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Image suggestions — shown when no image was uploaded */}
              {result.image_suggestions.length > 0 && (
                <Card>
                  <CardHeader className="pb-2 pt-3 px-4">
                    <CardTitle className="text-sm flex items-center gap-1.5">
                      <Lightbulb className="h-4 w-4 text-amber-500" />
                      Image Ideas
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 space-y-2">
                    {result.image_suggestions.map((s, i) => (
                      <div key={i} className="rounded-md border p-3 space-y-0.5">
                        <p className="text-sm font-medium">{s.description}</p>
                        <p className="text-xs text-muted-foreground">
                          Style: {s.style} · Mood: {s.mood}
                        </p>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* ── Save to Campaign ── */}
              <Card className={`border-primary/40 ${saved ? "bg-green-50 dark:bg-green-950/20" : ""}`}>
                <CardHeader className="pb-2 pt-3 px-4">
                  <CardTitle className="text-sm flex items-center gap-1.5">
                    <CalendarDays className="h-4 w-4 text-primary" />
                    Save to Campaign
                    {saved && <Badge variant="default" className="ml-auto text-xs bg-green-600">Saved ✓</Badge>}
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4 space-y-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs">Campaign</Label>
                    <select
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                      value={campaignId}
                      onChange={(e) => setCampaignId(e.target.value)}
                    >
                      <option value="">— Select campaign —</option>
                      {(campaigns ?? []).map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs flex items-center gap-1.5">
                      <CalendarDays className="h-3 w-3" /> Schedule date & time
                      <span className="text-muted-foreground font-normal">(optional)</span>
                    </Label>
                    <Input
                      type="datetime-local"
                      value={scheduledAt}
                      onChange={(e) => setScheduledAt(e.target.value)}
                      min={new Date(Date.now() + 60_000).toISOString().slice(0, 16)}
                    />
                  </div>

                  <div className="flex gap-2">
                    <Button
                      size="sm" className="flex-1 gap-1.5"
                      disabled={saving || !campaignId || !scheduledAt || saved}
                      onClick={() => handleSave(true)}
                    >
                      {saving
                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        : <CalendarDays className="h-3.5 w-3.5" />}
                      Save & Schedule
                    </Button>
                    <Button
                      size="sm" variant="outline" className="flex-1 gap-1.5"
                      disabled={saving || !campaignId || saved}
                      onClick={() => handleSave(false)}
                    >
                      <BookmarkPlus className="h-3.5 w-3.5" />
                      Save as Draft
                    </Button>
                  </div>
                  {saved && (
                    <p className="text-xs text-center text-muted-foreground">
                      Find it in Approvals or the Calendar to review and publish.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            <Card className="min-h-[300px] flex items-center justify-center">
              <div className="text-center text-muted-foreground space-y-2">
                <Sparkles className="h-8 w-8 mx-auto opacity-30" />
                <p className="text-sm">Fill in the brief and click Generate.</p>
                <p className="text-xs opacity-70">Upload an image to include it in the generation.</p>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* ── History panel ── */}
      {history.length > 0 && (
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold flex items-center gap-1.5">
              <History className="h-4 w-4 text-muted-foreground" />
              History
              <Badge variant="secondary" className="text-xs">{history.length}</Badge>
            </h3>
            <button onClick={clearHistory}
              className="text-xs text-muted-foreground hover:text-destructive transition-colors flex items-center gap-1">
              <Trash2 className="h-3 w-3" /> Clear all
            </button>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {history.map((entry) => (
              <div key={entry.id}
                className="group relative rounded-lg border bg-card p-3 hover:border-primary/50 transition-colors cursor-pointer"
                onClick={() => restoreFromHistory(entry)}
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <p className="text-xs font-medium line-clamp-2 flex-1">{entry.headline}</p>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteHistoryItem(entry.id); }}
                    className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-1">{entry.brief}</p>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-[10px] text-muted-foreground">
                    {new Date(entry.ts).toLocaleDateString("en-AU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span className="text-[10px] text-primary flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <RotateCcw className="h-2.5 w-2.5" /> Restore
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
