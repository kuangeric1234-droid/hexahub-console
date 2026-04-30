"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiClient } from "@/lib/api";

interface FetchedPost {
  platform:   string;
  text:       string;
  created_at: string | null;
}

export default function MetaCallbackPage() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Connecting to Meta…");

  useEffect(() => {
    const code  = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");

    if (error) {
      setStatus("error");
      setMessage(`Meta declined: ${searchParams.get("error_description") ?? error}`);
      return;
    }

    if (!code) {
      setStatus("error");
      setMessage("No authorisation code returned from Meta.");
      return;
    }

    // Validate state to prevent CSRF
    const savedState = localStorage.getItem("meta_oauth_state");
    if (state && savedState && state !== savedState) {
      setStatus("error");
      setMessage("OAuth state mismatch — please try again.");
      return;
    }
    localStorage.removeItem("meta_oauth_state");

    const redirectUri = `${window.location.origin}/auth/meta/callback`;

    setMessage("Fetching your posts…");

    apiClient
      .post<{ posts: FetchedPost[]; account_name: string | null }>(
        "/social/meta/fetch-posts",
        { code, redirect_uri: redirectUri }
      )
      .then((data) => {
        localStorage.setItem("meta_fetched_posts", JSON.stringify(data.posts));
        if (data.account_name) {
          localStorage.setItem("meta_account_name", data.account_name);
        }
        setStatus("success");
        setMessage(`Fetched ${data.posts.length} posts. Redirecting…`);
        setTimeout(() => router.replace("/brand?scanner=meta"), 1200);
      })
      .catch((err: Error) => {
        setStatus("error");
        setMessage(err.message ?? "Failed to fetch posts from Meta.");
      });
  }, [searchParams, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0F1117]">
      <div className="bg-[#1A1D27] rounded-2xl p-10 max-w-md w-full text-center shadow-xl">
        {status === "loading" && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 border-2 border-[#7F8B2F] border-t-transparent rounded-full animate-spin" />
            <p className="text-white text-lg font-medium">{message}</p>
          </div>
        )}
        {status === "success" && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-[#7F8B2F]/20 flex items-center justify-center">
              <svg className="w-6 h-6 text-[#7F8B2F]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-white text-lg font-medium">{message}</p>
          </div>
        )}
        {status === "error" && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
              <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <p className="text-red-400 text-lg font-medium">{message}</p>
            <button
              onClick={() => router.replace("/brand?tab=scanner")}
              className="mt-2 px-5 py-2 bg-[#7F8B2F] hover:bg-[#6a7526] text-white rounded-lg text-sm"
            >
              Back to Brand
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
