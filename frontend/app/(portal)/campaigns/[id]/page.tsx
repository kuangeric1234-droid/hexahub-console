"use client";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Megaphone, Clock, Pause, Play, Loader2 } from "lucide-react";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api";
import { Campaign, Post } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";

const STATUS_VARIANT: Record<string, "default" | "success" | "warning" | "destructive" | "secondary"> = {
  draft:      "secondary",
  active:     "warning",
  paused:     "default",
  completed:  "success",
  archived:   "secondary",
  pending:    "warning",
  approved:   "success",
  rejected:   "destructive",
  scheduled:  "default",
  published:  "success",
  failed:     "destructive",
  generating: "warning",
};

const PLATFORM_COLORS: Record<string, string> = {
  linkedin:       "bg-blue-100 text-blue-800",
  instagram:      "bg-pink-100 text-pink-800",
  blog:           "bg-indigo-100 text-indigo-800",
  xiaohongshu:    "bg-red-100 text-red-800",
  wechat_moments: "bg-green-100 text-green-800",
};

function PostRow({ post }: { post: Post }) {
  return (
    <div className="flex items-start gap-3 py-3">
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${PLATFORM_COLORS[post.platform] ?? "bg-muted text-muted-foreground"}`}>
        {post.platform.replace("_", " ")}
      </span>
      <div className="flex-1 min-w-0">
        {post.copy ? (
          <p className="text-sm line-clamp-2">{post.copy}</p>
        ) : (
          <p className="text-sm text-muted-foreground italic">Generating…</p>
        )}
        {post.scheduled_at && (
          <p className="text-xs text-muted-foreground mt-0.5">
            <Clock className="inline h-3 w-3 mr-1" />
            {format(new Date(post.scheduled_at), "MMM d, yyyy 'at' h:mm a")}
          </p>
        )}
      </div>
      <div className="flex gap-1.5 shrink-0">
        <Badge variant={STATUS_VARIANT[post.approval_status] ?? "default"} className="text-[10px] capitalize">
          {post.approval_status}
        </Badge>
      </div>
    </div>
  );
}

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router  = useRouter();
  const qc      = useQueryClient();

  const { data: campaign, isLoading: loadingCampaign } = useQuery<Campaign>({
    queryKey: ["campaigns", id],
    queryFn:  () => apiClient.get<Campaign>(`/campaigns/${id}`),
  });

  const { data: posts, isLoading: loadingPosts } = useQuery<Post[]>({
    queryKey: ["posts", id],
    queryFn:  () => apiClient.get<Post[]>(`/posts?campaign_id=${id}&page_size=50`),
    enabled:  !!id,
    refetchInterval: (query) => {
      const data = query.state.data as Post[] | undefined;
      const hasGenerating = data?.some((p) => !p.copy);
      return hasGenerating ? 8_000 : false;
    },
  });

  const pauseMutation = useMutation({
    mutationFn: () => apiClient.post(`/campaigns/${id}/pause`),
    onSuccess:  () => { toast.info("Workflow paused"); qc.invalidateQueries({ queryKey: ["campaigns", id] }); },
  });
  const resumeMutation = useMutation({
    mutationFn: () => apiClient.post(`/campaigns/${id}/resume`),
    onSuccess:  () => { toast.success("Workflow resumed"); qc.invalidateQueries({ queryKey: ["campaigns", id] }); },
  });

  const generatingCount = posts?.filter((p) => !p.copy).length ?? 0;
  const isGenerating    = generatingCount > 0;

  if (loadingCampaign) {
    return (
      <div className="space-y-4 max-w-4xl">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 rounded-lg" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <p className="text-muted-foreground">Campaign not found.</p>
        <Button variant="outline" onClick={() => router.push("/campaigns")}>Back to Campaigns</Button>
      </div>
    );
  }

  const pendingPosts   = posts?.filter((p) => p.approval_status === "pending")   ?? [];
  const approvedPosts  = posts?.filter((p) => p.approval_status === "approved")  ?? [];
  const rejectedPosts  = posts?.filter((p) => p.approval_status === "rejected")  ?? [];

  return (
    <div className="space-y-5 max-w-4xl">
      {/* Back + header */}
      <div>
        <Button variant="ghost" size="sm" className="mb-3 -ml-2 gap-1.5 text-muted-foreground"
          onClick={() => router.push("/campaigns")}>
          <ArrowLeft className="h-4 w-4" /> Campaigns
        </Button>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold">{campaign.name}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">{campaign.objective}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0 mt-1">
            {isGenerating && (
              <>
                <span className="text-xs text-muted-foreground flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {generatingCount} generating
                </span>
                <Button size="sm" variant="outline" className="gap-1.5 h-7 text-xs"
                  disabled={pauseMutation.isPending}
                  onClick={() => pauseMutation.mutate()}>
                  <Pause className="h-3 w-3" /> Pause
                </Button>
              </>
            )}
            {!isGenerating && posts && posts.length > 0 && (
              <Button size="sm" variant="outline" className="gap-1.5 h-7 text-xs"
                disabled={resumeMutation.isPending}
                onClick={() => resumeMutation.mutate()}>
                <Play className="h-3 w-3" /> Resume
              </Button>
            )}
            <Badge variant={STATUS_VARIANT[campaign.status] ?? "default"} className="capitalize">
              {campaign.status}
            </Badge>
          </div>
        </div>
      </div>

      {/* Meta cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card>
          <CardContent className="p-3">
            <p className="text-xs text-muted-foreground mb-1">Start date</p>
            <p className="text-sm font-medium">{formatDate(campaign.start_date)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <p className="text-xs text-muted-foreground mb-1">End date</p>
            <p className="text-sm font-medium">{formatDate(campaign.end_date)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <p className="text-xs text-muted-foreground mb-1">Total posts</p>
            <p className="text-sm font-medium">{posts?.length ?? "—"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <p className="text-xs text-muted-foreground mb-1">Pending approval</p>
            <p className="text-sm font-medium">{pendingPosts.length}</p>
          </CardContent>
        </Card>
      </div>

      {/* Brief */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Brief</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{campaign.brief}</p>
        </CardContent>
      </Card>

      {/* Posts */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">Posts</CardTitle>
            <div className="flex gap-2 text-xs text-muted-foreground">
              <span className="text-amber-600">{pendingPosts.length} pending</span>
              <span className="text-green-600">{approvedPosts.length} approved</span>
              {rejectedPosts.length > 0 && <span className="text-red-600">{rejectedPosts.length} rejected</span>}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loadingPosts ? (
            <div className="space-y-2 p-4">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 rounded" />)}
            </div>
          ) : !posts || posts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center text-sm text-muted-foreground gap-2">
              <Megaphone className="h-8 w-8 opacity-30" />
              <p>No posts yet. They&apos;ll appear here once the AI workflow generates them.</p>
              <p className="text-xs">This requires an Anthropic or OpenAI API key in the backend .env file.</p>
            </div>
          ) : (
            <div className="divide-y px-4">
              {posts.map((post) => <PostRow key={post.id} post={post} />)}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Actions */}
      {pendingPosts.length > 0 && (
        <div className="flex gap-2">
          <Button onClick={() => router.push("/approvals")}>
            Review {pendingPosts.length} pending post{pendingPosts.length !== 1 ? "s" : ""}
          </Button>
        </div>
      )}
    </div>
  );
}
