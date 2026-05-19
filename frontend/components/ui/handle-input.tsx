"use client";

/**
 * HandleInput — Instagram/social handle field with:
 *  - Saved handles dropdown (localStorage)
 *  - URL paste extraction (instagram.com/handle → handle)
 *  - Format validation (no spaces, valid chars)
 *  - Save / remove handles from list
 */

import { useEffect, useRef, useState } from "react";
import { Check, Star, StarOff, X } from "lucide-react";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "hexa_saved_handles";

function loadSaved(): string[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]"); }
  catch { return []; }
}

function saveToDB(handles: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(handles));
}

function extractHandle(raw: string): string {
  const trimmed = raw.trim();
  // Instagram / TikTok / LinkedIn URL → extract last path segment
  try {
    const url = new URL(trimmed);
    const parts = url.pathname.replace(/\/$/, "").split("/").filter(Boolean);
    if (parts.length > 0) return parts[parts.length - 1].replace(/^@/, "");
  } catch { /* not a URL */ }
  return trimmed.replace(/^@/, "");
}

function isValid(handle: string): boolean {
  return /^[a-zA-Z0-9._]{1,30}$/.test(handle);
}

interface HandleInputProps {
  value:       string;
  onChange:    (val: string) => void;
  placeholder?: string;
  className?:  string;
}

export function HandleInput({ value, onChange, placeholder = "creatorhandle", className }: HandleInputProps) {
  const [saved,       setSaved]       = useState<string[]>([]);
  const [open,        setOpen]        = useState(false);
  const [filter,      setFilter]      = useState("");
  const containerRef                  = useRef<HTMLDivElement>(null);

  useEffect(() => { setSaved(loadSaved()); }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handle    = extractHandle(value);
  const valid     = handle.length > 0 && isValid(handle);
  const isSaved   = saved.includes(handle);
  const filtered  = saved.filter(h => h.toLowerCase().includes(filter.toLowerCase()));

  function handleChange(raw: string) {
    setFilter(raw.replace(/^@/, ""));
    onChange(raw);
    setOpen(true);
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData("text");
    if (text.includes("/")) {
      e.preventDefault();
      const extracted = extractHandle(text);
      onChange(extracted);
      setFilter(extracted);
      setOpen(false);
    }
  }

  function select(h: string) {
    onChange(h);
    setFilter(h);
    setOpen(false);
  }

  function toggleSave() {
    const next = isSaved
      ? saved.filter(h => h !== handle)
      : [...saved, handle];
    setSaved(next);
    saveToDB(next);
  }

  function removeSaved(h: string, e: React.MouseEvent) {
    e.stopPropagation();
    const next = saved.filter(s => s !== h);
    setSaved(next);
    saveToDB(next);
  }

  const showDropdown = open && (filtered.length > 0 || filter.length === 0 && saved.length > 0);

  return (
    <div ref={containerRef} className="relative">
      <div className="relative flex items-center">
        <span className="absolute left-3 text-sm text-muted-foreground select-none">@</span>
        <input
          className={cn(
            "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors",
            "pl-7 pr-9",
            "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
            handle.length > 0 && !valid && "border-destructive focus-visible:ring-destructive",
            handle.length > 0 && valid  && "border-green-500 focus-visible:ring-green-500",
            className,
          )}
          value={value.replace(/^@/, "")}
          placeholder={placeholder}
          onChange={(e) => handleChange(e.target.value)}
          onPaste={handlePaste}
          onFocus={() => setOpen(true)}
        />
        {/* Save star button */}
        {valid && (
          <button
            type="button"
            onClick={toggleSave}
            title={isSaved ? "Remove from saved" : "Save handle"}
            className="absolute right-2.5 text-muted-foreground hover:text-amber-500 transition-colors"
          >
            {isSaved
              ? <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
              : <Star className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>

      {/* Validation hint */}
      {handle.length > 0 && !valid && (
        <p className="text-[10px] text-destructive mt-0.5">
          Handles can only contain letters, numbers, periods and underscores (max 30 chars)
        </p>
      )}
      {handle.length > 0 && valid && (
        <p className="text-[10px] text-green-600 mt-0.5 flex items-center gap-1">
          <Check className="h-2.5 w-2.5" /> Valid handle
          {isSaved && " · saved"}
        </p>
      )}

      {/* Dropdown */}
      {showDropdown && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md overflow-hidden">
          {filtered.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">No saved handles yet — type a handle and click ★ to save it</p>
          ) : (
            <ul className="max-h-48 overflow-y-auto py-1">
              {filtered.map((h) => (
                <li key={h}>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between px-3 py-1.5 text-sm hover:bg-muted transition-colors"
                    onClick={() => select(h)}
                  >
                    <span className="flex items-center gap-2">
                      <Star className="h-3 w-3 fill-amber-400 text-amber-400 shrink-0" />
                      @{h}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => removeSaved(h, e)}
                      className="text-muted-foreground hover:text-destructive transition-colors ml-2"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
