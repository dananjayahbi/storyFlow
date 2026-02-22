import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface RenderStatusBadgeProps {
  status: "DRAFT" | "PROCESSING" | "COMPLETED" | "FAILED";
  className?: string;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; emoji: string; variant: "default" | "secondary" | "destructive" | "outline"; extraClasses?: string }
> = {
  DRAFT: {
    label: "Draft",
    emoji: "📝",
    variant: "secondary",
  },
  PROCESSING: {
    label: "Rendering",
    emoji: "⚙️",
    variant: "outline",
    extraClasses: "border-yellow-500 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 animate-pulse",
  },
  COMPLETED: {
    label: "Completed",
    emoji: "✅",
    variant: "outline",
    extraClasses: "border-green-500 bg-green-500/10 text-green-700 dark:text-green-400",
  },
  FAILED: {
    label: "Failed",
    emoji: "❌",
    variant: "destructive",
  },
};

/**
 * RenderStatusBadge — a color-coded badge reflecting the project's
 * current render status. Used in the project detail header and
 * dashboard project cards.
 */
export default function RenderStatusBadge({
  status,
  className,
}: RenderStatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  // Fallback for unknown status values
  if (!config) {
    return (
      <Badge variant="secondary" className={className}>
        {status}
      </Badge>
    );
  }

  return (
    <Badge
      variant={config.variant}
      className={cn(config.extraClasses, className)}
    >
      {config.label} {config.emoji}
    </Badge>
  );
}
