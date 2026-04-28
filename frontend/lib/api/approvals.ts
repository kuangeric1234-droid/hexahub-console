import { api } from "./client";
import type {
  ApprovalHistoryItem,
  ApprovalQueueCount,
  ApprovalQueueItem,
  PaginationParams,
  Post,
} from "@/lib/types";

export async function getApprovalQueue(
  params?: PaginationParams & { platform?: string }
): Promise<ApprovalQueueItem[]> {
  const { data } = await api.get<ApprovalQueueItem[]>("/approvals/queue", { params });
  return data;
}

export async function getApprovalCount(): Promise<ApprovalQueueCount> {
  const { data } = await api.get<ApprovalQueueCount>("/approvals/queue/count");
  return data;
}

export async function getApprovalHistory(
  params?: PaginationParams & { reviewer?: string; decision?: string }
): Promise<ApprovalHistoryItem[]> {
  const { data } = await api.get<ApprovalHistoryItem[]>("/approvals/history", { params });
  return data;
}

export async function approvePost(postId: string, feedback?: string): Promise<Post> {
  const { data } = await api.post<Post>(`/posts/${postId}/approve`, { feedback });
  return data;
}

export async function rejectPost(postId: string, feedback: string): Promise<Post> {
  const { data } = await api.post<Post>(`/posts/${postId}/reject`, { feedback });
  return data;
}

export async function batchApprove(
  postIds: string[],
  feedback?: string
): Promise<{ approved: string[]; failed: { post_id: string; reason: string }[] }> {
  const { data } = await api.post("/approvals/batch-approve", { post_ids: postIds, feedback });
  return data;
}
