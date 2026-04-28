"use client";
import { useQuery } from "@tanstack/react-query";
import { Bot, CheckCircle2, XCircle, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api";
import { AgentLog } from "@/lib/types";
import { formatDateTime, truncate } from "@/lib/utils";

const STATUS_ICON: Record<AgentLog["status"], React.ReactNode> = {
  success: <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />,
  failed:  <XCircle     className="h-3.5 w-3.5 text-red-600"   />,
  running: <Clock       className="h-3.5 w-3.5 text-amber-500"  />,
};

const STATUS_VARIANT: Record<AgentLog["status"], "success" | "destructive" | "warning"> = {
  success: "success",
  failed:  "destructive",
  running: "warning",
};

function LogEntry({ log }: { log: AgentLog }) {
  const outputSummary = log.output_json
    ? truncate(JSON.stringify(log.output_json), 140)
    : null;

  return (
    <div className="flex gap-3 py-3 px-4">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted">
        <Bot className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">{log.agent_name}</span>
          <span className="text-xs text-muted-foreground">{log.task}</span>
          <Badge
            variant={STATUS_VARIANT[log.status]}
            className="ml-auto flex items-center gap-1 text-xs"
          >
            {STATUS_ICON[log.status]}
            {log.status}
          </Badge>
        </div>
        {outputSummary && (
          <p className="text-xs text-muted-foreground">{outputSummary}</p>
        )}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {log.timestamp && <span>{formatDateTime(log.timestamp)}</span>}
          {log.duration_ms != null && (
            <span>{(log.duration_ms / 1000).toFixed(2)}s</span>
          )}
          {typeof log.input_json?.skills_loaded === "object" &&
            Array.isArray(log.input_json.skills_loaded) &&
            log.input_json.skills_loaded.length > 0 && (
              <span className="text-blue-600">
                skills: {(log.input_json.skills_loaded as string[]).join(", ")}
              </span>
            )}
        </div>
      </div>
    </div>
  );
}

export default function LogsPage() {
  const { data: logs, isLoading } = useQuery<AgentLog[]>({
    queryKey: ["agent-logs"],
    queryFn:  () => apiClient.get<AgentLog[]>("/agent-logs"),
    refetchInterval: 10_000,
  });

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Agent Logs</h2>
        {logs && (
          <span className="text-xs text-muted-foreground">
            {logs.length} entries · auto-refresh 10s
          </span>
        )}
      </div>

      <div className="rounded-lg border bg-card divide-y">
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex gap-3 p-3">
              <Skeleton className="h-8 w-8 rounded-full shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-full" />
              </div>
            </div>
          ))
        ) : !logs || logs.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground text-center">No agent activity yet.</p>
        ) : (
          logs.map((log) => <LogEntry key={log.id} log={log} />)
        )}
      </div>
    </div>
  );
}
