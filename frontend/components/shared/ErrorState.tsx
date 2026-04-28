import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorStateProps {
  message?:  string;
  onRetry?:  () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center px-4">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 mb-3">
        <AlertTriangle className="h-5 w-5 text-destructive" />
      </div>
      <p className="text-sm font-medium mb-1">Something went wrong</p>
      <p className="text-xs text-muted-foreground mb-4 max-w-xs">
        {message ?? "Failed to load data. Check your network connection or backend status."}
      </p>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RefreshCw className="h-3.5 w-3.5 mr-2" /> Retry
        </Button>
      )}
    </div>
  );
}
