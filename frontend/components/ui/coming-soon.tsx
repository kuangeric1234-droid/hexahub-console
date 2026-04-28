import { Construction } from "lucide-react";

interface ComingSoonProps {
  title: string;
  description?: string;
}

export function ComingSoon({ title, description }: ComingSoonProps) {
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="flex flex-col items-center justify-center rounded-lg border bg-muted/20 py-20 text-center gap-3">
        <Construction className="h-10 w-10 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">Coming soon</p>
          {description && (
            <p className="text-xs text-muted-foreground mt-1 max-w-xs">{description}</p>
          )}
        </div>
      </div>
    </div>
  );
}
