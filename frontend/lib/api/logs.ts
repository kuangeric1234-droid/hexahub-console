import { api } from "./client";
import type { AgentLog, PaginationParams } from "@/lib/types";

export async function listAgentLogs(
  params?: PaginationParams & { agent_name?: string; status?: string }
): Promise<AgentLog[]> {
  const { data } = await api.get<AgentLog[]>("/logs/agent-runs", { params });
  return data;
}

export async function getAgentLog(logId: string): Promise<AgentLog> {
  const { data } = await api.get<AgentLog>(`/logs/agent-runs/${logId}`);
  return data;
}

export async function getWorkflowLogs(threadId: string): Promise<AgentLog[]> {
  const { data } = await api.get<AgentLog[]>(`/logs/workflow/${threadId}`);
  return data;
}
