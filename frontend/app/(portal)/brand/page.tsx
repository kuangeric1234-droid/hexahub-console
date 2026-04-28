"use client";
import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Save, Loader2, BookOpen, Sparkles, Copy, Check, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api/client";
import { BrandContext, SkillList } from "@/lib/types";

// ── Brand data from Hexa guidelines ──────────────────────────────────────────

const BRAND_COLOURS = [
  {
    name:  "Black",
    hex:   "#000000",
    cmyk:  "C0 M0 Y0 K100",
    rgb:   "R0 G0 B0",
    role:  "Primary — logo, typography, primary text",
  },
  {
    name:  "Hexa Green",
    hex:   "#7F8B2F",
    cmyk:  "C30 M04 Y100 K20",
    rgb:   "R127 G139 B47",
    pms:   "PMS 383U / 2306C",
    role:  "Brand accent — never use for logo or typography",
  },
  {
    name:  "White",
    hex:   "#FFFFFF",
    cmyk:  "C0 M0 Y0 K0",
    rgb:   "R255 G255 B255",
    role:  "Primary background",
  },
  {
    name:  "Light Grey",
    hex:   "#EFEDF2",
    cmyk:  "C7 M6 Y5 K10",
    rgb:   "R239 G237 B242",
    pms:   "PMS 2330U at 50%",
    role:  "Supporting background / accent",
  },
];

const TYPOGRAPHY = [
  {
    name:      "Rework Micro",
    weight:    "Semibold",
    role:      "Headlines",
    style:     "Uppercase · Tracking −25 · Leading 120%",
    fallback:  "Arial Bold (All Caps)",
    specimen:  "HEXA HUB",
    className: "font-bold uppercase tracking-widest text-2xl",
  },
  {
    name:      "Big Daily Short",
    weight:    "Extralight",
    role:      "Feature / Display",
    style:     "Sentence case · Tracking −15 · Leading 95%",
    fallback:  "Times New Roman Regular",
    specimen:  "Success through collaboration",
    className: "font-extralight text-3xl italic",
  },
  {
    name:      "GT America",
    weight:    "Thin",
    role:      "Body Copy",
    style:     "Uppercase · Tracking +15 · Leading 120%",
    fallback:  "Arial Regular",
    specimen:  "PEOPLE. PLACE. CULTURE. LEGACY.",
    className: "font-thin uppercase tracking-wider text-base",
  },
  {
    name:      "Hiragino Sans GB",
    weight:    "W3 / W6",
    role:      "Chinese Body / Headlines",
    style:     "Left justified · Leading 130%",
    fallback:  "System Chinese font",
    specimen:  "精诚所至，金石为开",
    className: "text-xl",
  },
];

const BRAND_DNA_TEMPLATE = `# HEXA — Brand Context

## Brand Positioning
Australian diversified property and fund management group that creates enduring value through innovation and collaboration.

## Brand Promise
Success through collaboration.

## Brand Vision
To create a holistic property platform that delivers lasting and mutual benefit for all.

## Brand Purpose
Through a commitment to innovation and collaboration, we create transformative spaces that have a positive impact and meaningful benefit to our clients and community.

## Brand Archetype
The Creator — celebrates the creative process, inspires self-expression, brings vision to life. Communication should stir desire for the creative process and inspire audiences to express their nature to the best of their ability.

## Brand Values
United. Collaborative. Harmony. Ethical. Trustworthy. Virtuous Together.

## Brand Pillars
People. Place. Culture. Legacy.

## Brand Character
Contemporary, confident, formal and considered.

## Brand Associations
Australian. Trustworthy. Caring. Quality. Innovative. Different.

## Target Audience
Primary: First home buyers/families. Professionals & young couples. Local & International investors.
Secondary: Family Offices & Institutions. Banks. Sales channels & partners.

## Tone of Voice
- Professional yet warm
- Collaborative, never boastful
- Confident without superlatives
- Bilingual-aware (Anglo/Asian cultural balance, sensitivity index 9/10)
- Never use: co-working space, game-changing, revolutionary, synergy, all-in-one

## Master Brand Colours
- Black #000000 — primary colour for logo and all typography
- Hexa Green #7F8B2F (PMS 383U) — brand accent only, NEVER for logo or body text
- White #FFFFFF — primary background
- Light Grey #EFEDF2 (PMS 2330U 50%) — supporting background

## Typography
- Headlines: Rework Micro Semibold, uppercase, tracking −25
- Feature/Display: Big Daily Short Extralight, sentence case
- Body: GT America Thin, uppercase, tracking +15
- Chinese: Hiragino Sans GB W6 (headlines) / W3 (body)

## Photography Pillars
- People: staff, collaborators, community — clean natural light, desaturated tones
- Place: hyperlocal Melbourne, embedded in landscape — warm natural lighting
- Culture: art, traditions, food, festivals — vibrant, colourful, energetic
- Process: models, plans, site visits — elevated, professionally shot
- Projects: interiors/exteriors — soft morning light, gentle desaturated tones

## Design Principles
- Premium/Luxury index: 8/10
- Design led. Contemporary culture.
- Consistent signatures. Never stretch, rotate or modify the brandmark.
- Bilingual brandmark available for Chinese-language contexts.
- Monogram (H×X): people connected / virtuous together — used as signature detail.
`;

const TABS = [
  { id: "colours",    label: "Colours"    },
  { id: "typography", label: "Typography" },
  { id: "marks",      label: "Brand Marks"},
  { id: "context",    label: "AI Context" },
  { id: "skills",     label: "Skills"     },
] as const;

type TabId = typeof TABS[number]["id"];

// ── Component ─────────────────────────────────────────────────────────────────

export default function BrandKitPage() {
  const [tab,     setTab]     = useState<TabId>("colours");
  const [content, setContent] = useState("");
  const [dirty,   setDirty]   = useState(false);
  const [copied,  setCopied]  = useState(false);

  const { data: ctx, isLoading: loadingCtx, refetch } = useQuery<BrandContext>({
    queryKey: ["brand", "context"],
    queryFn:  async () => (await api.get<BrandContext>("/brand/context")).data,
  });

  const { data: skills, isLoading: loadingSkills } = useQuery<SkillList>({
    queryKey: ["brand", "skills"],
    queryFn:  async () => (await api.get<SkillList>("/brand/skills")).data,
  });

  useEffect(() => {
    if (ctx?.content) { setContent(ctx.content); setDirty(false); }
  }, [ctx]);

  const save = useMutation({
    mutationFn: async () => (await api.put("/brand/context", { content })).data,
    onSuccess:  () => { toast.success("Brand context saved — AI agents will use this from now on."); setDirty(false); refetch(); },
    onError:    () => toast.error("Failed to save brand context."),
  });

  function loadTemplate() {
    setContent(BRAND_DNA_TEMPLATE);
    setDirty(true);
    toast.success("Brand DNA template loaded — edit as needed and click Save.");
  }

  function handleCopy() {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="space-y-4 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Brand Kit</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Hexa Brand Guidelines 2024 — colour, typography, marks, and AI context
          </p>
        </div>
        {tab === "context" && (
          <div className="flex gap-2">
            {dirty && (
              <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending} className="gap-1.5">
                {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b overflow-x-auto">
        {TABS.map(({ id, label }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`shrink-0 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* ── COLOURS ─────────────────────────────────────────────────────────── */}
      {tab === "colours" && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Master brand colours. Our palette is black and white with green and light grey accents.
            Green should be specified as PMS 383U for offset print.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {BRAND_COLOURS.map((c) => (
              <Card key={c.name} className="overflow-hidden">
                <div
                  className="h-24 w-full border-b"
                  style={{ backgroundColor: c.hex }}
                />
                <CardContent className="p-3 space-y-1.5">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold">{c.name}</p>
                    <button
                      className="text-xs text-muted-foreground hover:text-foreground font-mono"
                      onClick={() => { navigator.clipboard.writeText(c.hex); toast.success(`Copied ${c.hex}`); }}
                    >
                      {c.hex}
                    </button>
                  </div>
                  {c.pms && <p className="text-xs text-muted-foreground">{c.pms}</p>}
                  <p className="text-xs text-muted-foreground">{c.cmyk}</p>
                  <p className="text-xs text-muted-foreground">{c.rgb}</p>
                  <Separator />
                  <p className="text-xs text-muted-foreground leading-snug">{c.role}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="border-amber-200 bg-amber-50">
            <CardContent className="p-3">
              <p className="text-xs text-amber-800">
                <strong>Rule:</strong> The Hexa logo and all supporting typography must only be used in black or white.
                Never use Hexa Green (#7F8B2F) or Light Grey for the logo or typography.
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── TYPOGRAPHY ──────────────────────────────────────────────────────── */}
      {tab === "typography" && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Hexa uses four typefaces across EN and ZH communications.
            Web-safe fallbacks are specified for environments where brand fonts are unavailable.
          </p>
          <div className="space-y-3">
            {TYPOGRAPHY.map((t) => (
              <Card key={t.name}>
                <CardContent className="p-4">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                    <div className="sm:w-48 shrink-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold">{t.name}</p>
                        <Badge variant="secondary" className="text-[10px]">{t.weight}</Badge>
                      </div>
                      <p className="text-xs font-medium text-primary">{t.role}</p>
                      <p className="text-xs text-muted-foreground">{t.style}</p>
                      <p className="text-xs text-muted-foreground">Fallback: {t.fallback}</p>
                    </div>
                    <div className="flex-1 rounded-md bg-muted/50 p-4">
                      <p className={t.className} style={{ fontFamily: t.name === "Big Daily Short Extralight" ? "Times New Roman, serif" : undefined }}>
                        {t.specimen}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="border-muted">
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground">
                <strong>Hierarchy:</strong> Headlines use Rework Micro Semibold at ~33% of feature text size.
                Feature text (Big Daily Short) is ~300% of headline. Sub-headings are ~75% of body text.
                For Chinese, replace all EN typefaces with Hiragino Sans GB W6 (headings) and W3 (body).
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── BRAND MARKS ─────────────────────────────────────────────────────── */}
      {tab === "marks" && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            The Hexa brandmark and monogram. Only reproduce from finished artwork provided by brand guardians.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Primary Brand Mark</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex h-32 items-center justify-center rounded-lg bg-black">
                  <span className="text-white text-3xl font-bold tracking-[0.3em]">HEXA</span>
                </div>
                <div className="flex h-16 items-center justify-center rounded-lg bg-white border">
                  <span className="text-black text-3xl font-bold tracking-[0.3em]">HEXA</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Clear space: minimum 2× cap height on all sides.
                  Never use colour combinations, stretch, rotate, or modify.
                </p>
                <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed p-3 text-xs text-muted-foreground hover:bg-muted transition-colors">
                  <Upload className="h-4 w-4" />
                  Upload logo file (SVG, PNG)
                  <input type="file" accept=".svg,.png,.ai,.pdf" className="hidden" onChange={() => toast.info("Logo upload requires the assets backend to be configured.")} />
                </label>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Monogram</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex h-32 items-center justify-center rounded-lg bg-black">
                  <span className="text-white text-6xl font-thin" style={{ letterSpacing: "-0.05em" }}>H×</span>
                </div>
                <div className="flex h-16 items-center justify-center rounded-lg bg-[#7F8B2F]">
                  <span className="text-white text-3xl font-thin" style={{ letterSpacing: "-0.05em" }}>H×</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Stylised H and X — represents people connected / virtuous together (吉祥结).
                  Minimum distance from brandmark: 6× height of letter H.
                  Exclusively for Hexa branded applications.
                </p>
                <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed p-3 text-xs text-muted-foreground hover:bg-muted transition-colors">
                  <Upload className="h-4 w-4" />
                  Upload monogram file (SVG, PNG)
                  <input type="file" accept=".svg,.png,.ai,.pdf" className="hidden" onChange={() => toast.info("Monogram upload requires the assets backend to be configured.")} />
                </label>
              </CardContent>
            </Card>
          </div>

          <Card className="border-amber-200 bg-amber-50">
            <CardContent className="p-3 space-y-1">
              <p className="text-xs font-semibold text-amber-800">Incorrect use reminders</p>
              <ul className="text-xs text-amber-800 space-y-0.5 list-disc list-inside">
                <li>Never substitute typefaces in the brandmark</li>
                <li>Never use colour combinations (black and white only for logo)</li>
                <li>Never stretch, rotate, or skew the brandmark</li>
                <li>Never use letters separately — always together</li>
                <li>Never alter the position or stack elements differently</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ── AI CONTEXT ──────────────────────────────────────────────────────── */}
      {tab === "context" && (
        <div className="space-y-3">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              This document is injected into <strong>every AI agent</strong> as brand knowledge.
              The AI will use these colours, tone, values, and pillars when generating all content.
            </p>
            <div className="flex shrink-0 gap-2">
              <Button variant="outline" size="sm" onClick={handleCopy} className="gap-1.5">
                {copied ? <><Check className="h-3.5 w-3.5" /> Copied</> : <><Copy className="h-3.5 w-3.5" /> Copy</>}
              </Button>
              {(!content || content.trim().length < 50) && (
                <Button variant="outline" size="sm" onClick={loadTemplate} className="gap-1.5">
                  <Sparkles className="h-3.5 w-3.5" /> Load Hexa template
                </Button>
              )}
            </div>
          </div>

          {loadingCtx ? (
            <Skeleton className="h-[500px] rounded-lg" />
          ) : (
            <Textarea
              className="min-h-[500px] font-mono text-xs resize-none"
              placeholder="Click 'Load Hexa template' to pre-populate with your brand guidelines, then edit and save."
              value={content}
              onChange={(e) => { setContent(e.target.value); setDirty(true); }}
            />
          )}

          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">{content.length} characters</p>
            {dirty && (
              <div className="flex items-center gap-3">
                <p className="text-xs text-amber-600">Unsaved changes</p>
                <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending} className="gap-1.5">
                  {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save to AI
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── SKILLS ──────────────────────────────────────────────────────────── */}
      {tab === "skills" && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Marketing skill files loaded into agent prompts. Custom skills in{" "}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">backend/skills/custom/</code>{" "}
            override external ones.
          </p>
          {loadingSkills ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {[1,2,3,4].map((i) => <Skeleton key={i} className="h-14 rounded-lg" />)}
            </div>
          ) : !skills ? (
            <p className="text-sm text-muted-foreground">Could not load skills.</p>
          ) : (
            <>
              {skills.custom.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Custom (override priority)</h3>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {skills.custom.map((name) => (
                      <Card key={name} className="border-primary/30">
                        <CardContent className="p-3 flex items-center gap-2">
                          <Sparkles className="h-4 w-4 text-primary shrink-0" />
                          <span className="text-sm font-medium">{name}</span>
                          <Badge variant="secondary" className="ml-auto text-[10px]">custom</Badge>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
              {skills.external.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">External (marketing submodule)</h3>
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {skills.external.map((name) => (
                      <Card key={name}>
                        <CardContent className="p-3 flex items-center gap-2">
                          <BookOpen className="h-4 w-4 text-muted-foreground shrink-0" />
                          <span className="text-sm">{name}</span>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
              {skills.external.length === 0 && skills.custom.length === 0 && (
                <Card>
                  <CardContent className="flex flex-col items-center py-10 text-center gap-2">
                    <BookOpen className="h-8 w-8 text-muted-foreground opacity-40" />
                    <p className="text-sm text-muted-foreground">No skills found.</p>
                    <p className="text-xs text-muted-foreground max-w-sm">
                      Add markdown files to <code className="bg-muted px-1 rounded">backend/skills/custom/</code> or initialise the marketing submodule.
                    </p>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
