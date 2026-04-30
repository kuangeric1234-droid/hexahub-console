"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ImageOff, FolderOpen, Loader2, Download, ChevronLeft,
  Search, Film, Image as ImageIcon, Grid3X3, Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api";
import { Asset } from "@/lib/types";
import { toast } from "sonner";
import { format } from "date-fns";

// ── Types ─────────────────────────────────────────────────────────────────────

interface DriveFile {
  id:            string;
  name:          string;
  mimeType:      string;
  size:          number | null;
  modifiedTime:  string | null;
  is_folder:     boolean;
  thumbnail_url: string | null;
}

interface DriveFilesResponse {
  files:           DriveFile[];
  next_page_token: string | null;
  folder_id:       string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Drive file card ───────────────────────────────────────────────────────────

function DriveCard({
  file, onNavigate, onImport, importing,
}: {
  file:       DriveFile;
  onNavigate: (id: string) => void;
  onImport:   (file: DriveFile) => void;
  importing:  boolean;
}) {
  const [imgError, setImgError] = useState(false);
  const isVideo = file.mimeType.startsWith("video/");
  const isImage = file.mimeType.startsWith("image/");

  if (file.is_folder) {
    return (
      <button
        onClick={() => onNavigate(file.id)}
        className="flex flex-col items-center gap-2 p-4 rounded-xl border bg-card hover:bg-muted/40 transition-colors text-center group"
      >
        <FolderOpen className="h-10 w-10 text-amber-500 group-hover:text-amber-400" />
        <p className="text-xs font-medium line-clamp-2 leading-tight">{file.name}</p>
      </button>
    );
  }

  return (
    <div className="flex flex-col rounded-xl border bg-card overflow-hidden group">
      {/* Thumbnail */}
      <div className="relative aspect-square bg-muted flex items-center justify-center overflow-hidden">
        {file.thumbnail_url && !imgError ? (
          <img
            src={file.thumbnail_url}
            alt={file.name}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : isVideo ? (
          <Film className="h-8 w-8 text-muted-foreground" />
        ) : isImage ? (
          <ImageIcon className="h-8 w-8 text-muted-foreground" />
        ) : (
          <ImageOff className="h-8 w-8 text-muted-foreground" />
        )}
        {isVideo && (
          <div className="absolute top-2 left-2">
            <Badge className="text-xs bg-black/60 hover:bg-black/60">Video</Badge>
          </div>
        )}
      </div>

      {/* Info + action */}
      <div className="p-2.5 space-y-2">
        <p className="text-xs font-medium line-clamp-2 leading-tight">{file.name}</p>
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">{formatBytes(file.size)}</span>
          <Button
            size="sm"
            variant="outline"
            className="h-6 text-xs px-2 gap-1"
            onClick={() => onImport(file)}
            disabled={importing}
          >
            {importing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
            Import
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Library asset card ────────────────────────────────────────────────────────

function AssetCard({ asset }: { asset: Asset }) {
  const [imgError, setImgError] = useState(false);
  const isVideo = asset.type === "video";

  return (
    <div className="flex flex-col rounded-xl border bg-card overflow-hidden">
      <div className="relative aspect-square bg-muted flex items-center justify-center overflow-hidden">
        {!isVideo && !imgError ? (
          <img src={asset.url} alt={asset.name ?? ""} className="w-full h-full object-cover"
            onError={() => setImgError(true)} />
        ) : isVideo ? (
          <Film className="h-8 w-8 text-muted-foreground" />
        ) : (
          <ImageOff className="h-8 w-8 text-muted-foreground" />
        )}
        {asset.tags.includes("google-drive") && (
          <div className="absolute top-2 right-2">
            <Badge className="text-xs bg-blue-500/80 hover:bg-blue-500/80">Drive</Badge>
          </div>
        )}
      </div>
      <div className="p-2.5">
        <p className="text-xs font-medium line-clamp-1">{asset.name ?? "Untitled"}</p>
        {asset.created_at && (
          <p className="text-xs text-muted-foreground mt-0.5">
            {format(new Date(asset.created_at), "MMM d, yyyy")}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AssetsPage() {
  const queryClient = useQueryClient();
  const [tab,          setTab]          = useState<"library" | "drive">("library");
  const [folderStack,  setFolderStack]  = useState<{ id: string; name: string }[]>([]);
  const [driveSearch,  setDriveSearch]  = useState("");
  const [typeFilter,   setTypeFilter]   = useState("all");
  const [importingId,  setImportingId]  = useState<string | null>(null);
  const [libSearch,    setLibSearch]    = useState("");
  const [pageToken,    setPageToken]    = useState<string | null>(null);

  const currentFolderId = folderStack.length > 0
    ? folderStack[folderStack.length - 1].id
    : null;

  // Library query
  const { data: libraryAssets, isLoading: libLoading } = useQuery<Asset[]>({
    queryKey: ["assets", libSearch],
    queryFn:  () => apiClient.get<Asset[]>(`/assets?page_size=100${libSearch ? `&search=${encodeURIComponent(libSearch)}` : ""}`),
    enabled:  tab === "library",
    staleTime: 30_000,
  });

  // Drive query
  const driveKey = ["drive", currentFolderId, typeFilter, driveSearch, pageToken];
  const { data: driveData, isLoading: driveLoading } = useQuery<DriveFilesResponse>({
    queryKey: driveKey,
    queryFn: () => {
      const params = new URLSearchParams({ page_size: "60" });
      if (currentFolderId)  params.set("folder_id",   currentFolderId);
      if (typeFilter !== "all") params.set("type",    typeFilter);
      if (driveSearch)      params.set("search",      driveSearch);
      if (pageToken)        params.set("page_token",  pageToken);
      return apiClient.get<DriveFilesResponse>(`/drive/files?${params}`);
    },
    enabled:  tab === "drive",
    staleTime: 60_000,
  });

  const importMutation = useMutation({
    mutationFn: (file: DriveFile) =>
      apiClient.post("/drive/import", {
        file_id:   file.id,
        file_name: file.name,
        mime_type: file.mimeType,
      }),
    onSuccess: (_, file) => {
      toast.success(`Imported: ${file.name}`);
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      setImportingId(null);
    },
    onError: (err: Error, file) => {
      toast.error(`Import failed: ${err.message}`);
      setImportingId(null);
    },
  });

  function handleImport(file: DriveFile) {
    setImportingId(file.id);
    importMutation.mutate(file);
  }

  function handleNavigate(id: string, name: string = "Folder") {
    setFolderStack((s) => [...s, { id, name }]);
    setPageToken(null);
  }

  function handleBack() {
    setFolderStack((s) => s.slice(0, -1));
    setPageToken(null);
  }

  return (
    <div className="space-y-5 pb-12">

      {/* Header + tabs */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
          <button
            onClick={() => setTab("library")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${tab === "library" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
          >
            <Grid3X3 className="h-3.5 w-3.5" /> Library
          </button>
          <button
            onClick={() => { setTab("drive"); setFolderStack([]); setPageToken(null); }}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${tab === "drive" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
          >
            <FolderOpen className="h-3.5 w-3.5" /> Google Drive
          </button>
        </div>
      </div>

      {/* ── Library tab ── */}
      {tab === "library" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input placeholder="Search assets…" className="pl-8 text-sm h-8"
                value={libSearch} onChange={(e) => setLibSearch(e.target.value)} />
            </div>
            <span className="text-xs text-muted-foreground">
              {libraryAssets?.length ?? 0} assets
            </span>
          </div>

          {libLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {[...Array(12)].map((_, i) => <Skeleton key={i} className="aspect-square rounded-xl" />)}
            </div>
          ) : !libraryAssets?.length ? (
            <div className="text-center py-20 text-muted-foreground">
              <ImageOff className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">No assets yet.</p>
              <p className="text-xs mt-1">Import from Google Drive or upload directly to a post.</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {libraryAssets.map((a) => <AssetCard key={a.id} asset={a} />)}
            </div>
          )}
        </div>
      )}

      {/* ── Drive tab ── */}
      {tab === "drive" && (
        <div className="space-y-4">

          {/* Breadcrumb + controls */}
          <div className="flex flex-wrap items-center gap-2">
            {folderStack.length > 0 && (
              <Button size="sm" variant="ghost" className="gap-1.5 h-8" onClick={handleBack}>
                <ChevronLeft className="h-3.5 w-3.5" /> Back
              </Button>
            )}
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <span className="cursor-pointer hover:text-foreground"
                onClick={() => { setFolderStack([]); setPageToken(null); }}>
                Root
              </span>
              {folderStack.map((f, i) => (
                <span key={f.id} className="flex items-center gap-1">
                  <span>/</span>
                  <span className={i === folderStack.length - 1 ? "text-foreground font-medium" : "cursor-pointer hover:text-foreground"}
                    onClick={() => { setFolderStack((s) => s.slice(0, i + 1)); setPageToken(null); }}>
                    {f.name}
                  </span>
                </span>
              ))}
            </div>

            <div className="ml-auto flex items-center gap-2">
              <select
                className="rounded-md border border-input bg-background px-2 py-1 text-xs"
                value={typeFilter}
                onChange={(e) => { setTypeFilter(e.target.value); setPageToken(null); }}
              >
                <option value="all">All files</option>
                <option value="image">Images</option>
                <option value="video">Videos</option>
              </select>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input placeholder="Search…" className="pl-8 text-xs h-8 w-40"
                  value={driveSearch}
                  onChange={(e) => { setDriveSearch(e.target.value); setPageToken(null); }} />
              </div>
            </div>
          </div>

          {driveLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {[...Array(12)].map((_, i) => <Skeleton key={i} className="aspect-square rounded-xl" />)}
            </div>
          ) : !driveData?.files.length ? (
            <div className="text-center py-20 text-muted-foreground">
              <FolderOpen className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p className="text-sm">No files found.</p>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {driveData.files.map((f) => (
                  <DriveCard
                    key={f.id}
                    file={f}
                    onNavigate={(id) => handleNavigate(id, f.name)}
                    onImport={handleImport}
                    importing={importingId === f.id}
                  />
                ))}
              </div>
              {driveData.next_page_token && (
                <div className="flex justify-center pt-2">
                  <Button variant="outline" size="sm"
                    onClick={() => setPageToken(driveData.next_page_token)}>
                    Load more
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
