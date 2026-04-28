"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar, dateFnsLocalizer, Views } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { enUS } from "date-fns/locale";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { CalendarDays } from "lucide-react";
import { api } from "@/lib/api/client";
import { Campaign, CampaignCalendar, PostSlot } from "@/lib/types";
import "react-big-calendar/lib/css/react-big-calendar.css";

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 1 }),
  getDay,
  locales: { "en-US": enUS },
});

const PLATFORM_COLORS: Record<string, string> = {
  linkedin:       "#0077b5",
  instagram:      "#e1306c",
  blog:           "#6366f1",
  xiaohongshu:    "#ff2442",
  wechat_moments: "#07c160",
};

type CalEvent = {
  title:    string;
  start:    Date;
  end:      Date;
  platform: string;
  post:     PostSlot;
};

function buildEvents(data: CampaignCalendar): CalEvent[] {
  return data.posts
    .filter((p): p is PostSlot & { scheduled_at: string } => !!p.scheduled_at)
    .map((p) => {
      const start = new Date(p.scheduled_at);
      const end   = new Date(start.getTime() + 30 * 60_000);
      return {
        title:    `${p.platform.replace("_", " ")} — ${p.copy ? p.copy.slice(0, 35) + "…" : "Draft"}`,
        start, end,
        platform: p.platform,
        post:     p,
      };
    });
}

export default function CalendarPage() {
  const [selectedId, setSelectedId] = useState<string>("");
  const [selectedPost, setSelectedPost] = useState<PostSlot | null>(null);
  const [calDate, setCalDate] = useState(new Date());

  const { data: campaigns, isLoading: loadingCampaigns } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn:  async () => (await api.get<Campaign[]>("/campaigns")).data,
  });

  const { data: calData, isLoading: loadingCal } = useQuery<CampaignCalendar>({
    queryKey: ["calendar", selectedId],
    queryFn:  async () => (await api.get<CampaignCalendar>(`/campaigns/${selectedId}/calendar`)).data,
    enabled:  !!selectedId,
  });

  const events = calData ? buildEvents(calData) : [];

  return (
    <div className="space-y-4" style={{ height: "calc(100vh - 9rem)" }}>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Calendar</h2>
        <select
          className="rounded-md border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          value={selectedId}
          onChange={(e) => { setSelectedId(e.target.value); setSelectedPost(null); }}
        >
          <option value="">— Select campaign —</option>
          {(campaigns ?? []).map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>

        {/* Platform legend */}
        <div className="flex flex-wrap gap-3 ml-auto text-xs">
          {Object.entries(PLATFORM_COLORS).map(([p, color]) => (
            <span key={p} className="flex items-center gap-1.5 text-muted-foreground">
              <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
              {p.replace("_", " ")}
            </span>
          ))}
        </div>
      </div>

      {loadingCampaigns ? (
        <Skeleton className="h-full rounded-lg" />
      ) : !selectedId ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed text-center">
          <CalendarDays className="h-10 w-10 text-muted-foreground opacity-40" />
          <div>
            <p className="text-sm font-medium">Select a campaign</p>
            <p className="text-xs text-muted-foreground mt-1">
              Choose a campaign above to view its scheduled posts on the calendar.
            </p>
          </div>
        </div>
      ) : loadingCal ? (
        <Skeleton className="h-full rounded-lg" />
      ) : (
        <div className="flex gap-4 h-full">
          <div className="flex-1 rounded-lg border bg-card p-3 min-h-0">
            <Calendar
              localizer={localizer}
              events={events}
              defaultView={Views.MONTH}
              views={[Views.MONTH, Views.WEEK, Views.AGENDA]}
              date={calDate}
              onNavigate={(date) => setCalDate(date)}
              onSelectEvent={(e: CalEvent) => setSelectedPost(e.post)}
              eventPropGetter={(e: CalEvent) => ({
                style: {
                  backgroundColor: PLATFORM_COLORS[e.platform] ?? "#64748b",
                  border: "none",
                  borderRadius: "4px",
                  color: "#fff",
                  fontSize: "11px",
                  padding: "2px 5px",
                },
              })}
              style={{ height: "100%" }}
            />
          </div>

          {/* Post detail panel */}
          {selectedPost && (
            <div className="w-72 shrink-0">
              <Card className="h-full overflow-y-auto">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Post detail
                    </span>
                    <button className="text-xs text-muted-foreground hover:text-foreground"
                      onClick={() => setSelectedPost(null)}>✕</button>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <Badge variant="secondary" className="capitalize text-xs">
                      {selectedPost.platform.replace("_", " ")}
                    </Badge>
                    <Badge
                      variant={selectedPost.approval_status === "approved" ? "success"
                        : selectedPost.approval_status === "rejected" ? "destructive" : "warning"}
                      className="capitalize text-xs">
                      {selectedPost.approval_status}
                    </Badge>
                  </div>
                  {selectedPost.scheduled_at && (
                    <p className="text-xs text-muted-foreground">
                      📅 {format(new Date(selectedPost.scheduled_at), "MMM d, yyyy 'at' h:mm a")}
                    </p>
                  )}
                  {selectedPost.copy ? (
                    <p className="text-sm whitespace-pre-wrap">{selectedPost.copy}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">No copy generated yet.</p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
