"use client";
import { useQuery } from "@tanstack/react-query";
import { getApprovalCount } from "@/lib/api/approvals";
import { APPROVAL_POLL_INTERVAL_MS } from "@/lib/constants";

export function useApprovalCount() {
  return useQuery({
    queryKey:       ["approvals", "count"],
    queryFn:        getApprovalCount,
    refetchInterval: APPROVAL_POLL_INTERVAL_MS,
    select:          (data) => data.count,
    // Don't throw on error — sidebar badge failing silently is fine
    retry: false,
  });
}
