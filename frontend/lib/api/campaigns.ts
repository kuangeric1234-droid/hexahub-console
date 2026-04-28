import { api } from "./client";
import type {
  Campaign, CampaignCalendar, CampaignCreate, CampaignUpdate, PaginationParams,
} from "@/lib/types";

export async function listCampaigns(params?: PaginationParams & { status?: string }): Promise<Campaign[]> {
  const { data } = await api.get<Campaign[]>("/campaigns", { params });
  return data;
}

export async function getCampaign(id: string): Promise<Campaign> {
  const { data } = await api.get<Campaign>(`/campaigns/${id}`);
  return data;
}

export async function createCampaign(body: CampaignCreate): Promise<Campaign> {
  const { data } = await api.post<Campaign>("/campaigns", body);
  return data;
}

export async function updateCampaign(id: string, body: CampaignUpdate): Promise<Campaign> {
  const { data } = await api.patch<Campaign>(`/campaigns/${id}`, body);
  return data;
}

export async function deleteCampaign(id: string): Promise<void> {
  await api.delete(`/campaigns/${id}`);
}

export async function getCampaignCalendar(id: string): Promise<CampaignCalendar> {
  const { data } = await api.get<CampaignCalendar>(`/campaigns/${id}/calendar`);
  return data;
}

export async function getBilingualView(id: string): Promise<unknown> {
  const { data } = await api.get(`/campaigns/${id}/bilingual-view`);
  return data;
}

export async function regenerateCalendar(id: string): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>(`/campaigns/${id}/regenerate-calendar`);
  return data;
}
