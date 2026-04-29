from dataclasses import dataclass
from typing import Optional


@dataclass
class PublishResult:
    success: bool
    post_url: Optional[str] = None
    platform_post_id: Optional[str] = None
    error: Optional[str] = None
