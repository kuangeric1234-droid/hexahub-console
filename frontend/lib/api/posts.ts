import { api } from "./client";

export interface Post {
  id: string;
  campaign_id: string;
  platform: string;
  status: string;
  approval_status: string;
  copy: string | null;
  visual_url: string | null;
  scheduled_at: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export async function listPosts(params?: {
  campaign_id?: string;
  platform?: string;
  status?: string;
  page?: number;
}): Promise<Post[]> {
  const { data } = await api.get<Post[]>("/posts", { params });
  return data;
}

export async function getPost(id: string): Promise<Post> {
  const { data } = await api.get<Post>(`/posts/${id}`);
  return data;
}

export async function schedulePost(id: string, scheduledAt: Date): Promise<Post> {
  const { data } = await api.post<Post>(`/posts/${id}/schedule`, {
    scheduled_at: scheduledAt.toISOString(),
  });
  return data;
}

export async function publishNow(id: string): Promise<Post> {
  const { data } = await api.post<Post>(`/posts/${id}/publish-now`);
  return data;
}

export async function updatePost(id: string, body: Partial<Pick<Post, "copy" | "visual_url" | "scheduled_at">>): Promise<Post> {
  const { data } = await api.patch<Post>(`/posts/${id}`, body);
  return data;
}
