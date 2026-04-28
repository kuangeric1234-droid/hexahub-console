"use client";
import { useRef, useState } from "react";
import {
  Loader2, Sparkles, Copy, Check, Upload, X, Image as ImageIcon,
  LayoutGrid, Film, FileText, Lightbulb, Wand2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
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
  const [brief,       setBrief]       = useState("");
  const [result,      setResult]      = useState<AssistResult | null>(null);
  const [loading,     setLoading]     = useState(false);
  const [copied,      setCopied]      = useState(false);
  const [imageFile,   setImageFile]   = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [dragOver,    setDragOver]    = useState(false);
  const fileInputRef  = useRef<HTMLInputElement>(null);

  const platformKey = config.platform.toLowerCase().replace(" ", "_").replace("-", "_");

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

      const data = await apiClient.post<AssistResult>("/create/assisted", {
        platform:        platformKey,
        brief,
        image_base64,
        image_mime_type,
      });

      setResult(data);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setLoading(false);
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
    </div>
  );
}
