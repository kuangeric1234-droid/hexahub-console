"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Calendar, Clock, Send, Zap, CheckCircle2, XCircle, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { listPosts, schedulePost, publishNow, type Post } from "@/lib/api/posts";
import { apiErrorMessage } from "@/lib/api/client";

const PLATFORM_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  instagram: "Instagram",
  facebook: "Facebook",
  blog: "Blog",
  xiaohongshu: "Xiaohongshu",
  wechat_moments: "WeChat",
};

const STATUS_BADGE: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  approved:  { label: "Approved",  variant: "default" },
  scheduled: { label: "Scheduled", variant: "secondary" },
  published: { label: "Published", variant: "default" },
  failed:    { label: "Failed",    variant: "destructive" },
  draft:     { label: "Draft",     variant: "outline" },
  pending:   { label: "Pending",   variant: "outline" },
};

function formatDt(iso: string) {
  return new Date(iso).toLocaleString("en-AU", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function PostRow({ post, onScheduled, onPublished }: {
  post: Post;
  onScheduled: (p: Post) => void;
  onPublished: (p: Post) => void;
}) {
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [schedulingAt, setSchedulingAt] = useState("");
  const [loadingSchedule, setLoadingSchedule] = useState(false);
  const [loadingPublish, setLoadingPublish] = useState(false);

  const badge = STATUS_BADGE[post.status] ?? { label: post.status, variant: "outline" as const };
  const externalUrl = (post.metadata_json?.external_url as string) ?? null;
  const publishError = (post.metadata_json?.publish_error as string) ?? null;

  async function handleSchedule() {
    if (!schedulingAt) return;
    setLoadingSchedule(true);
    try {
      const updated = await schedulePost(post.id, new Date(schedulingAt));
      toast.success(`Scheduled for ${formatDt(updated.scheduled_at!)}`);
      setScheduleOpen(false);
      onScheduled(updated);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setLoadingSchedule(false);
    }
  }

  async function handlePublishNow() {
    setLoadingPublish(true);
    try {
      const updated = await publishNow(post.id);
      if (updated.status === "published") {
        toast.success("Published successfully!");
      } else {
        toast.error(`Publish failed: ${(updated.metadata_json?.publish_error as string) ?? "Unknown error"}`);
      }
      onPublished(updated);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setLoadingPublish(false);
    }
  }

  return (
    <>
      <div className="flex items-start gap-4 py-4 border-b last:border-0">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {PLATFORM_LABELS[post.platform] ?? post.platform}
            </span>
            <Badge variant={badge.variant} className="text-xs">{badge.label}</Badge>
          </div>
          <p className="text-sm line-clamp-2 text-foreground">
            {post.copy ?? <span className="text-muted-foreground italic">No copy yet</span>}
          </p>
          {post.scheduled_at && (
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {post.status === "published" ? "Published" : "Scheduled"}: {formatDt(post.scheduled_at)}
            </p>
          )}
          {externalUrl && (
            <a href={externalUrl} target="_blank" rel="noopener noreferrer"
               className="text-xs text-primary underline mt-1 inline-block">
              View post ↗
            </a>
          )}
          {publishError && (
            <p className="text-xs text-destructive mt-1">{publishError}</p>
          )}
        </div>

        {(post.status === "approved" || post.status === "scheduled") && (
          <div className="flex gap-2 shrink-0">
            {post.status === "approved" && (
              <>
                <Button size="sm" variant="outline" onClick={() => setScheduleOpen(true)}>
                  <Calendar className="h-3 w-3 mr-1" /> Schedule
                </Button>
                <Button size="sm" onClick={handlePublishNow} disabled={loadingPublish}>
                  {loadingPublish ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3 mr-1" />}
                  Publish now
                </Button>
              </>
            )}
            {post.status === "scheduled" && (
              <Button size="sm" variant="outline" onClick={handlePublishNow} disabled={loadingPublish}>
                {loadingPublish ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3 mr-1" />}
                Publish now
              </Button>
            )}
          </div>
        )}

        {post.status === "published" && (
          <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
        )}
        {post.status === "failed" && (
          <XCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
        )}
      </div>

      <Dialog open={scheduleOpen} onOpenChange={setScheduleOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule post</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm text-muted-foreground line-clamp-2">{post.copy}</p>
            <div className="space-y-1.5">
              <Label>Date &amp; time</Label>
              <Input
                type="datetime-local"
                value={schedulingAt}
                onChange={e => setSchedulingAt(e.target.value)}
                min={new Date(Date.now() + 60_000).toISOString().slice(0, 16)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setScheduleOpen(false)}>Cancel</Button>
            <Button onClick={handleSchedule} disabled={!schedulingAt || loadingSchedule}>
              {loadingSchedule && <Loader2 className="h-3 w-3 mr-2 animate-spin" />}
              Confirm schedule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function PublishPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  async function load() {
    setLoading(true);
    try {
      const all = await listPosts({ page: 1 });
      const publishable = all.filter(p =>
        ["approved", "scheduled", "published", "failed"].includes(p.status)
      );
      setPosts(publishable);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function updatePost(updated: Post) {
    setPosts(prev => prev.map(p => p.id === updated.id ? updated : p));
  }

  const filtered = filter === "all" ? posts : posts.filter(p => p.status === filter);

  const counts = {
    approved:  posts.filter(p => p.status === "approved").length,
    scheduled: posts.filter(p => p.status === "scheduled").length,
    published: posts.filter(p => p.status === "published").length,
    failed:    posts.filter(p => p.status === "failed").length,
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Publish</h1>
          <p className="text-muted-foreground text-sm mt-0.5">Schedule and publish approved posts</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { key: "approved",  label: "Ready",     color: "text-blue-500" },
          { key: "scheduled", label: "Scheduled",  color: "text-yellow-500" },
          { key: "published", label: "Published",  color: "text-green-500" },
          { key: "failed",    label: "Failed",     color: "text-red-500" },
        ].map(({ key, label, color }) => (
          <Card key={key}
            className={`cursor-pointer transition-colors ${filter === key ? "ring-2 ring-primary" : ""}`}
            onClick={() => setFilter(filter === key ? "all" : key)}>
            <CardHeader className="pb-1 pt-3 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3">
              <span className={`text-2xl font-bold ${color}`}>{counts[key as keyof typeof counts]}</span>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Post list */}
      <Card>
        <CardContent className="p-0 px-4">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading posts…
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground text-sm">
              {filter === "all"
                ? "No approved posts yet. Approve posts from the Approvals queue first."
                : `No ${filter} posts.`}
            </div>
          ) : (
            filtered.map(post => (
              <PostRow
                key={post.id}
                post={post}
                onScheduled={updatePost}
                onPublished={updatePost}
              />
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
