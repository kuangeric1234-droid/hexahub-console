"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

// ── Types ─────────────────────────────────────────────────────────────────────

interface MetaStatus {
  connected:    boolean;
  page_name:    string | null;
  ig_username:  string | null;
  connected_at: string | null;
}

// ── Integration card ──────────────────────────────────────────────────────────

function IntegrationCard({
  logo, name, description, connected, detail, onConnect, onDisconnect, connecting, comingSoon,
}: {
  logo:          React.ReactNode;
  name:          string;
  description:   string;
  connected:     boolean;
  detail?:       string;
  onConnect?:    () => void;
  onDisconnect?: () => void;
  connecting?:   boolean;
  comingSoon?:   boolean;
}) {
  return (
    <div className="flex items-center gap-4 p-5 rounded-xl border bg-card">
      <div className="h-11 w-11 rounded-xl flex items-center justify-center flex-shrink-0 border bg-muted/30 text-xl">
        {logo}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="font-medium text-sm">{name}</span>
          {connected && (
            <Badge className="text-xs bg-green-500/15 text-green-700 border-green-200 hover:bg-green-500/15">
              Connected
            </Badge>
          )}
          {comingSoon && <Badge variant="secondary" className="text-xs">Coming soon</Badge>}
        </div>
        <p className="text-xs text-muted-foreground">{description}</p>
        {detail && <p className="text-xs text-muted-foreground mt-0.5 font-medium">{detail}</p>}
      </div>
      <div className="flex-shrink-0">
        {comingSoon ? (
          <Button size="sm" variant="outline" disabled>Connect</Button>
        ) : connected ? (
          <Button size="sm" variant="outline" onClick={onDisconnect}
            className="text-destructive hover:text-destructive border-destructive/30">
            Disconnect
          </Button>
        ) : (
          <Button size="sm" onClick={onConnect} disabled={connecting} className="gap-1.5">
            {connecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plug className="h-3.5 w-3.5" />}
            Connect
          </Button>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  const queryClient = useQueryClient();
  const [connecting, setConnecting] = useState(false);

  const { data: metaStatus, isLoading } = useQuery<MetaStatus>({
    queryKey: ["meta-status"],
    queryFn:  () => apiClient.get("/social/meta/status"),
    staleTime: 30_000,
  });

  const disconnect = useMutation({
    mutationFn: () => apiClient.del("/social/meta/disconnect"),
    onSuccess:  () => {
      queryClient.invalidateQueries({ queryKey: ["meta-status"] });
      toast.success("Disconnected");
    },
    onError: () => toast.error("Failed to disconnect"),
  });

  async function handleMetaConnect() {
    setConnecting(true);
    try {
      const state       = crypto.randomUUID();
      const redirectUri = `${window.location.origin}/auth/meta/connect/callback`;
      localStorage.setItem("meta_connect_state", state);

      const { url } = await apiClient.get<{ url: string }>(
        `/social/meta/connect-url?redirect_uri=${encodeURIComponent(redirectUri)}&state=${state}`
      );

      const popup = window.open(url, "meta-connect", "width=620,height=720,left=200,top=80");
      if (!popup) {
        toast.error("Popup blocked — allow popups for this site and try again");
        setConnecting(false);
        return;
      }

      function onMessage(event: MessageEvent) {
        if (event.origin !== window.location.origin) return;
        if (event.data?.type !== "META_CONNECT_CALLBACK") return;
        window.removeEventListener("message", onMessage);
        setConnecting(false);
        if (event.data.error) {
          toast.error(`Connection failed: ${event.data.error}`);
        } else {
          queryClient.invalidateQueries({ queryKey: ["meta-status"] });
          toast.success(`Connected${event.data.page_name ? ` — ${event.data.page_name}` : ""}!`);
        }
      }
      window.addEventListener("message", onMessage);

      const poll = setInterval(() => {
        if (popup.closed) {
          clearInterval(poll);
          window.removeEventListener("message", onMessage);
          setConnecting(false);
        }
      }, 600);

    } catch {
      toast.error("Could not start connection — check META_APP_ID is configured");
      setConnecting(false);
    }
  }

  const metaDetail = metaStatus?.connected
    ? [metaStatus.page_name, metaStatus.ig_username ? `@${metaStatus.ig_username}` : null]
        .filter(Boolean).join(" · ")
    : undefined;

  const redirectUri = typeof window !== "undefined"
    ? `${window.location.origin}/auth/meta/connect/callback`
    : "https://hexahub-console.vercel.app/auth/meta/connect/callback";

  return (
    <div className="max-w-2xl mx-auto space-y-8 pb-12">

      <div>
        <h2 className="text-lg font-semibold">Integrations</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Connect your accounts to enable automatic publishing from the scheduler.
        </p>
      </div>

      {/* Social Media */}
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Social Media</p>
        {isLoading ? (
          <div className="h-20 rounded-xl border bg-card animate-pulse" />
        ) : (
          <IntegrationCard
            logo="📘"
            name="Meta — Instagram & Facebook"
            description="Publish to your Instagram Business account and Facebook Page."
            connected={!!metaStatus?.connected}
            detail={metaDetail}
            onConnect={handleMetaConnect}
            onDisconnect={() => disconnect.mutate()}
            connecting={connecting}
          />
        )}
        <IntegrationCard
          logo="in"
          name="LinkedIn"
          description="Publish to your LinkedIn profile or company page."
          connected={false}
          comingSoon
        />
      </div>

      <Separator />

      {/* Blog */}
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Blog</p>
        <IntegrationCard
          logo="✍️"
          name="WordPress"
          description="Publish blog posts directly to your WordPress site."
          connected={false}
          comingSoon
        />
      </div>

      <Separator />

      {/* Manual */}
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Manual Channels</p>
        <div className="flex items-center gap-4 p-5 rounded-xl border bg-card">
          <div className="h-11 w-11 rounded-xl flex items-center justify-center flex-shrink-0 border bg-muted/30 text-xl">小</div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="font-medium text-sm">Xiaohongshu & WeChat Moments</span>
              <Badge variant="secondary" className="text-xs">Webhook</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              No public API — posts are packaged and sent to your webhook for manual publishing.
            </p>
          </div>
        </div>
      </div>

      {/* Redirect URI reminder */}
      {!metaStatus?.connected && (
        <>
          <Separator />
          <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 p-4 space-y-2">
            <p className="text-xs font-semibold text-amber-800 dark:text-amber-400">Before connecting</p>
            <p className="text-xs text-amber-700 dark:text-amber-500">
              Add this URI to your Meta App → App Settings → Valid OAuth Redirect URIs:
            </p>
            <code className="text-xs bg-amber-100 dark:bg-amber-900/40 px-2 py-1 rounded block break-all text-amber-900 dark:text-amber-300">
              {redirectUri}
            </code>
          </div>
        </>
      )}

    </div>
  );
}
