"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCheck, XCircle, Loader2, Wand2, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api";
import { ApprovalQueueItem } from "@/lib/types";
import { formatDateTime, truncate } from "@/lib/utils";
import { toast } from "sonner";

function ApprovalCard({
  item,
  onApprove,
  onReject,
  onModify,
  deciding,
  modifying,
}: {
  item:      ApprovalQueueItem;
  onApprove: (id: string, feedback: string) => void;
  onReject:  (id: string, feedback: string) => void;
  onModify:  (id: string, instructions: string, onSuccess: (newCopy: string) => void) => void;
  deciding:  boolean;
  modifying: boolean;
}) {
  const [feedback,     setFeedback]     = useState("");
  const [showModify,   setShowModify]   = useState(false);
  const [instructions, setInstructions] = useState("");
  const [liveCopy,     setLiveCopy]     = useState(item.copy ?? "");

  function handleModify() {
    if (!instructions.trim()) return;
    onModify(item.post_id, instructions, (newCopy) => {
      setLiveCopy(newCopy);
      setInstructions("");
      setShowModify(false);
    });
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <div className="space-y-0.5">
            <p className="font-medium capitalize">{item.platform}</p>
            <p className="text-xs text-muted-foreground">{item.campaign_name}</p>
          </div>
          {item.created_at && (
            <span className="text-xs text-muted-foreground">{formatDateTime(item.created_at)}</span>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {liveCopy ? (
          <p className="text-sm whitespace-pre-wrap">{truncate(liveCopy, 300)}</p>
        ) : (
          <p className="text-sm text-muted-foreground italic">No copy yet.</p>
        )}
        {item.scheduled_at && (
          <Badge variant="secondary" className="text-xs">
            Scheduled: {formatDateTime(item.scheduled_at)}
          </Badge>
        )}

        {/* ── Modify section ── */}
        <Separator />
        <button
          className="flex w-full items-center justify-between text-xs text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => setShowModify(!showModify)}
        >
          <span className="flex items-center gap-1.5">
            <Wand2 className="h-3.5 w-3.5" /> Modify with AI
          </span>
          {showModify ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </button>

        {showModify && (
          <div className="space-y-2">
            <Textarea
              rows={2}
              placeholder="e.g. Add 3 relevant hashtags, make it shorter, add a CTA…"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="text-sm"
            />
            <Button
              size="sm"
              variant="outline"
              className="w-full gap-1.5"
              disabled={modifying || !instructions.trim()}
              onClick={handleModify}
            >
              {modifying
                ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Rewriting…</>
                : <><Wand2 className="h-3.5 w-3.5" /> Rewrite</>
              }
            </Button>
          </div>
        )}

        <Separator />
        <div className="space-y-1.5">
          <Label className="text-xs">Feedback</Label>
          <Textarea
            rows={2}
            placeholder="Optional for approval, required for rejection…"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            className="text-sm"
          />
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            className="flex-1 gap-1.5"
            disabled={deciding}
            onClick={() => onApprove(item.post_id, feedback)}
          >
            {deciding ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCheck className="h-4 w-4" />}
            Approve
          </Button>
          <Button
            size="sm"
            variant="destructive"
            className="flex-1 gap-1.5"
            disabled={deciding || !feedback.trim()}
            onClick={() => onReject(item.post_id, feedback)}
          >
            <XCircle className="h-4 w-4" />
            Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function ApprovalsPage() {
  const qc = useQueryClient();
  const [decidingId,  setDecidingId]  = useState<string | null>(null);
  const [modifyingId, setModifyingId] = useState<string | null>(null);

  const { data: queue, isLoading } = useQuery<ApprovalQueueItem[]>({
    queryKey: ["approvals", "queue"],
    queryFn:  () => apiClient.get<ApprovalQueueItem[]>("/approvals/queue"),
    refetchInterval: 15_000,
  });

  const approve = useMutation({
    mutationFn: ({ id, feedback }: { id: string; feedback: string }) =>
      apiClient.post(`/posts/${id}/approve`, { feedback: feedback || undefined }),
    onMutate:   ({ id }) => setDecidingId(id),
    onSuccess:  () => toast.success("Post approved"),
    onSettled:  () => { setDecidingId(null); qc.invalidateQueries({ queryKey: ["approvals"] }); },
  });

  const reject = useMutation({
    mutationFn: ({ id, feedback }: { id: string; feedback: string }) =>
      apiClient.post(`/posts/${id}/reject`, { feedback }),
    onMutate:   ({ id }) => setDecidingId(id),
    onSuccess:  () => toast.info("Rejected — AI is rewriting based on your feedback"),
    onSettled:  () => { setDecidingId(null); qc.invalidateQueries({ queryKey: ["approvals"] }); },
  });

  const modify = useMutation({
    mutationFn: ({ id, instructions }: { id: string; instructions: string }) =>
      apiClient.post<{ copy: string }>(`/posts/${id}/modify`, { instructions }),
    onMutate:   ({ id }) => setModifyingId(id),
    onSuccess:  () => toast.success("Copy updated — review and approve when ready"),
    onError:    () => toast.error("Rewrite failed — try again"),
    onSettled:  () => setModifyingId(null),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Approvals</h2>
        {queue && queue.length > 0 && (
          <Badge variant="warning">{queue.length} pending</Badge>
        )}
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-64 rounded-lg" />)}
        </div>
      ) : !queue || queue.length === 0 ? (
        <p className="text-sm text-muted-foreground">No posts pending approval.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {queue.map((item) => (
            <ApprovalCard
              key={item.post_id}
              item={item}
              deciding={decidingId === item.post_id}
              modifying={modifyingId === item.post_id}
              onApprove={(id, feedback) => approve.mutate({ id, feedback })}
              onReject={(id, feedback)  => reject.mutate({ id, feedback })}
              onModify={(id, instructions, onSuccess) =>
                modify.mutate({ id, instructions }, { onSuccess: (data) => onSuccess(data.copy) })
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
