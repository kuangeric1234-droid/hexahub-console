"use client";
/**
 * OAuth callback for the publishing connection flow.
 * Meta redirects here after the user approves publishing permissions.
 * If opened as a popup, posts result to the opener and closes itself.
 * If opened as a full page (e.g. redirect), shows status and navigates back.
 */
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiClient } from "@/lib/api";

function ConnectCallbackInner() {
  const searchParams = useSearchParams();
  const router       = useRouter();
  const [status,  setStatus]  = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("Connecting your account…");

  useEffect(() => {
    const code  = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");

    function sendToOpener(payload: Record<string, unknown>) {
      if (window.opener) {
        window.opener.postMessage({ type: "META_CONNECT_CALLBACK", ...payload }, window.location.origin);
        window.close();
      } else {
        // Fallback — not in a popup, navigate back to integrations
        if (payload.error) {
          router.replace("/publish/integrations?error=connect_failed");
        } else {
          router.replace("/publish/integrations?connected=true");
        }
      }
    }

    if (error) {
      setStatus("error");
      setMessage(searchParams.get("error_description") ?? "Meta declined the request.");
      sendToOpener({ error });
      return;
    }

    if (!code) {
      setStatus("error");
      setMessage("No authorisation code returned from Meta.");
      sendToOpener({ error: "no_code" });
      return;
    }

    // CSRF check
    const savedState = localStorage.getItem("meta_connect_state");
    if (state && savedState && state !== savedState) {
      setStatus("error");
      setMessage("State mismatch — please try again.");
      sendToOpener({ error: "state_mismatch" });
      return;
    }
    localStorage.removeItem("meta_connect_state");

    const redirectUri = `${window.location.origin}/auth/meta/connect/callback`;

    apiClient
      .post<{ connected: boolean; page_name?: string | null; ig_username?: string | null }>(
        "/social/meta/connect",
        { code, redirect_uri: redirectUri }
      )
      .then((data) => {
        setStatus("success");
        setMessage(`Connected${data.page_name ? ` — ${data.page_name}` : ""}!`);
        sendToOpener({ connected: true, page_name: data.page_name, ig_username: data.ig_username });
      })
      .catch((err: Error) => {
        setStatus("error");
        setMessage(err.message ?? "Failed to connect account.");
        sendToOpener({ error: err.message });
      });
  }, [searchParams, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0F1117]">
      <div className="bg-[#1A1D27] rounded-2xl p-10 max-w-md w-full text-center shadow-xl">
        {status === "loading" && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-white text-lg font-medium">{message}</p>
          </div>
        )}
        {status === "success" && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
              <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
            <button onClick={() => router.replace("/publish/integrations")}
              className="mt-2 px-5 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg text-sm">
              Back to Integrations
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function MetaConnectCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-[#0F1117]">
        <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <ConnectCallbackInner />
    </Suspense>
  );
}
