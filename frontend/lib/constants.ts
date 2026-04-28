export const PLATFORMS = {
  linkedin:       { label: "LinkedIn",        color: "#0077b5", bgClass: "bg-[#0077b5]" },
  blog:           { label: "Blog",            color: "#6366f1", bgClass: "bg-indigo-500"  },
  instagram:      { label: "Instagram",       color: "#e1306c", bgClass: "bg-pink-500"    },
  xiaohongshu:    { label: "Xiaohongshu",    color: "#ff2442", bgClass: "bg-red-500"     },
  wechat_moments: { label: "WeChat Moments", color: "#07c160", bgClass: "bg-green-500"   },
} as const;

export type PlatformKey = keyof typeof PLATFORMS;

export const STATUS_BADGE = {
  draft:      { label: "Draft",     variant: "secondary"    },
  active:     { label: "Active",    variant: "warning"      },
  paused:     { label: "Paused",    variant: "secondary"    },
  completed:  { label: "Completed", variant: "success"      },
  archived:   { label: "Archived",  variant: "secondary"    },
  pending:    { label: "Pending",   variant: "warning"      },
  approved:   { label: "Approved",  variant: "success"      },
  rejected:   { label: "Rejected",  variant: "destructive"  },
  scheduled:  { label: "Scheduled", variant: "default"      },
  published:  { label: "Published", variant: "success"      },
  failed:     { label: "Failed",    variant: "destructive"  },
  generating: { label: "Generating",variant: "warning"      },
} as const;

export const APPROVAL_POLL_INTERVAL_MS = 30_000;
export const COMPLIANCE_DEBOUNCE_MS    = 500;
export const SEARCH_DEBOUNCE_MS        = 300;
export const STALE_TIME_DEFAULT_MS     = 30_000;
export const STALE_TIME_STATIC_MS      = 5 * 60_000;
