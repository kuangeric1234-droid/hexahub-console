"use client";
import { useState, useCallback } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckCircle2, XCircle, AlertTriangle, Shield } from "lucide-react";
import { api } from "@/lib/api/client";
import { ComplianceCheckResult, ComplianceFlag } from "@/lib/types";
import { COMPLIANCE_DEBOUNCE_MS } from "@/lib/constants";

const SEVERITY_STYLE: Record<string, { badge: string; bar: string }> = {
  critical: { badge: "bg-red-100 text-red-800 border-red-200",    bar: "bg-red-500"    },
  high:     { badge: "bg-orange-100 text-orange-800 border-orange-200", bar: "bg-orange-500" },
  medium:   { badge: "bg-amber-100 text-amber-800 border-amber-200",  bar: "bg-amber-400"  },
  low:      { badge: "bg-blue-100 text-blue-800 border-blue-200",   bar: "bg-blue-400"   },
};

const LANGUAGES = [
  { value: "zh-CN", label: "Chinese 中文" },
  { value: "en",    label: "English"      },
];

function HighlightedText({ text, flags }: { text: string; flags: ComplianceFlag[] }) {
  if (!flags.length) return <span className="whitespace-pre-wrap text-sm">{text}</span>;

  const sorted  = [...flags].sort((a, b) => a.position - b.position);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  for (const flag of sorted) {
    if (flag.position > cursor) {
      parts.push(<span key={`t-${cursor}`}>{text.slice(cursor, flag.position)}</span>);
    }
    const style = SEVERITY_STYLE[flag.severity] ?? SEVERITY_STYLE.medium;
    parts.push(
      <mark key={`f-${flag.position}`}
        className={`rounded px-0.5 ${style.badge} border`}
        title={`${flag.severity}: ${flag.category}`}>
        {text.slice(flag.position, flag.position + flag.length)}
      </mark>
    );
    cursor = flag.position + flag.length;
  }
  if (cursor < text.length) parts.push(<span key="tail">{text.slice(cursor)}</span>);

  return <p className="whitespace-pre-wrap text-sm leading-7">{parts}</p>;
}

export default function ComplianceCheckerPage() {
  const [text,     setText]     = useState("");
  const [language, setLanguage] = useState("zh-CN");
  const [result,   setResult]   = useState<ComplianceCheckResult | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [timer,    setTimer]    = useState<ReturnType<typeof setTimeout> | null>(null);

  const check = useCallback(async (value: string, lang: string) => {
    if (!value.trim()) { setResult(null); return; }
    setLoading(true);
    try {
      const { data } = await api.post<ComplianceCheckResult>("/compliance/check", {
        text: value, languages: [lang],
      });
      setResult(data);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, []);

  function handleChange(value: string) {
    setText(value);
    if (timer) clearTimeout(timer);
    const t = setTimeout(() => check(value, language), COMPLIANCE_DEBOUNCE_MS);
    setTimer(t);
  }

  function handleLanguageChange(lang: string) {
    setLanguage(lang);
    if (text.trim()) check(text, lang);
  }

  const flagsBySeverity = result?.flags.reduce<Record<string, ComplianceFlag[]>>((acc, f) => {
    acc[f.severity] = [...(acc[f.severity] ?? []), f];
    return acc;
  }, {}) ?? {};

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            Compliance Checker
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Paste marketing copy to scan for sensitive words (违禁词). Results appear as you type.
          </p>
        </div>
        <div className="flex gap-1.5">
          {LANGUAGES.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => handleLanguageChange(value)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium border transition-colors ${
                language === value
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border hover:bg-muted"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Input */}
        <div className="space-y-2">
          <Textarea
            className="min-h-[280px] text-sm resize-none"
            placeholder={language === "zh-CN"
              ? "粘贴营销文案，即时检测违禁词…\n\n例如：我们是最好的产品，第一品牌"
              : "Paste marketing copy to check for compliance issues…\n\nExample: This game-changing solution is world-class"}
            value={text}
            onChange={(e) => handleChange(e.target.value)}
          />
          <p className="text-xs text-muted-foreground text-right">{text.length} characters</p>
        </div>

        {/* Results */}
        <div className="space-y-3">
          {/* Status banner */}
          {loading ? (
            <div className="flex items-center gap-2 rounded-lg border p-3">
              <Skeleton className="h-5 w-5 rounded-full" />
              <Skeleton className="h-4 w-32" />
            </div>
          ) : result ? (
            <div className={`flex items-center gap-2 rounded-lg border p-3 ${
              result.passed
                ? "border-green-200 bg-green-50 text-green-800"
                : "border-red-200 bg-red-50 text-red-800"
            }`}>
              {result.passed
                ? <><CheckCircle2 className="h-5 w-5 shrink-0" /><span className="text-sm font-medium">No issues found — looks good!</span></>
                : <><XCircle className="h-5 w-5 shrink-0" /><span className="text-sm font-medium">{result.flags.length} issue{result.flags.length !== 1 ? "s" : ""} found</span></>
              }
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-lg border border-dashed p-3 text-muted-foreground">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span className="text-sm">Results appear here as you type.</span>
            </div>
          )}

          {/* Highlighted preview */}
          {text && result && result.flags.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wide">Preview with highlights</CardTitle>
              </CardHeader>
              <CardContent>
                <HighlightedText text={text} flags={result.flags} />
              </CardContent>
            </Card>
          )}

          {/* Flagged words */}
          {result && result.flags.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wide">Flagged Words</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {["critical", "high", "medium", "low"].map((sev) => {
                  const flags = flagsBySeverity[sev];
                  if (!flags?.length) return null;
                  const style = SEVERITY_STYLE[sev];
                  return (
                    <div key={sev}>
                      <p className="text-xs font-medium capitalize text-muted-foreground mb-1">{sev}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {flags.map((f, i) => (
                          <span key={i} className={`rounded border px-2 py-0.5 text-xs font-medium ${style.badge}`}>
                            {f.word}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          )}

          {/* Suggestions */}
          {result && result.suggestions.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground uppercase tracking-wide">Suggestions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1.5">
                {result.suggestions.map((s, i) => (
                  <p key={i} className="text-xs text-muted-foreground flex gap-2">
                    <span className="shrink-0 text-amber-500">→</span>{s}
                  </p>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
