import { type LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label:       string;
  value:       string | number;
  icon:        LucideIcon;
  iconClass?:  string;
  sub?:        string;
  loading?:    boolean;
}

export function KpiCard({ label, value, icon: Icon, iconClass, sub, loading }: KpiCardProps) {
  if (loading) {
    return (
      <Card>
        <CardContent className="p-4 space-y-2">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-7 w-12" />
          <Skeleton className="h-3 w-32" />
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-2">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <div className={cn("flex h-7 w-7 items-center justify-center rounded-md bg-primary/10", iconClass)}>
            <Icon className="h-3.5 w-3.5 text-primary" />
          </div>
        </div>
        <p className="text-2xl font-bold tracking-tight">{value}</p>
        {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}
