"""
Sensitive words seed data.

Imported by run_seeds.py. Not auto-applied — run explicitly.

Schema: (word, language, severity, category)
Severity: low | medium | high | critical
"""

SENSITIVE_WORDS: list[dict] = [
    # ── Chinese: absolute superlatives ─────────────────────────────────────
    # XHS and WeChat auto-flag these; platforms may restrict distribution
    {"word": "最",         "language": "zh-CN", "severity": "high",     "category": "absolute_claim"},
    {"word": "第一",       "language": "zh-CN", "severity": "high",     "category": "absolute_claim"},
    {"word": "唯一",       "language": "zh-CN", "severity": "high",     "category": "absolute_claim"},
    {"word": "顶级",       "language": "zh-CN", "severity": "high",     "category": "absolute_claim"},
    {"word": "最佳",       "language": "zh-CN", "severity": "high",     "category": "absolute_claim"},
    {"word": "最好",       "language": "zh-CN", "severity": "high",     "category": "absolute_claim"},
    {"word": "最便宜",     "language": "zh-CN", "severity": "high",     "category": "absolute_claim"},
    {"word": "最高级",     "language": "zh-CN", "severity": "high",     "category": "absolute_claim"},
    {"word": "最低价",     "language": "zh-CN", "severity": "high",     "category": "absolute_claim"},
    {"word": "史无前例",   "language": "zh-CN", "severity": "medium",   "category": "absolute_claim"},

    # ── Chinese: government / authority claims ──────────────────────────────
    {"word": "国家级",     "language": "zh-CN", "severity": "high",     "category": "regulatory"},
    {"word": "国家认证",   "language": "zh-CN", "severity": "critical", "category": "regulatory"},
    {"word": "政府推荐",   "language": "zh-CN", "severity": "critical", "category": "regulatory"},
    {"word": "官方指定",   "language": "zh-CN", "severity": "high",     "category": "regulatory"},

    # ── Chinese: medical / health claims ───────────────────────────────────
    {"word": "治愈",       "language": "zh-CN", "severity": "critical", "category": "medical_claim"},
    {"word": "根治",       "language": "zh-CN", "severity": "critical", "category": "medical_claim"},
    {"word": "特效",       "language": "zh-CN", "severity": "critical", "category": "medical_claim"},
    {"word": "立即见效",   "language": "zh-CN", "severity": "critical", "category": "medical_claim"},
    {"word": "无副作用",   "language": "zh-CN", "severity": "critical", "category": "medical_claim"},
    {"word": "药到病除",   "language": "zh-CN", "severity": "critical", "category": "medical_claim"},

    # ── Chinese: financial guarantee / investment ──────────────────────────
    {"word": "投资保证",   "language": "zh-CN", "severity": "critical", "category": "regulatory"},
    {"word": "稳赚",       "language": "zh-CN", "severity": "critical", "category": "regulatory"},
    {"word": "零风险",     "language": "zh-CN", "severity": "critical", "category": "regulatory"},
    {"word": "保证盈利",   "language": "zh-CN", "severity": "critical", "category": "regulatory"},
    {"word": "百分百回报", "language": "zh-CN", "severity": "critical", "category": "regulatory"},

    # ── English: absolute claims ───────────────────────────────────────────
    {"word": "guaranteed results",   "language": "en", "severity": "medium", "category": "absolute_claim"},
    {"word": "100% success",         "language": "en", "severity": "medium", "category": "absolute_claim"},
    {"word": "always works",         "language": "en", "severity": "low",    "category": "absolute_claim"},

    # ── English: medical / health ──────────────────────────────────────────
    {"word": "cure",     "language": "en", "severity": "high", "category": "medical_claim"},
    {"word": "treat",    "language": "en", "severity": "high", "category": "medical_claim"},
    {"word": "diagnose", "language": "en", "severity": "high", "category": "medical_claim"},
    {"word": "heal",     "language": "en", "severity": "high", "category": "medical_claim"},

    # ── English: Hexa HUB brand-forbidden phrases ──────────────────────────
    # From Brand Brain §9
    {"word": "game-changing",                    "language": "en", "severity": "high",   "category": "brand_forbidden"},
    {"word": "revolutionary",                    "language": "en", "severity": "medium", "category": "brand_forbidden"},
    {"word": "disruptive",                       "language": "en", "severity": "medium", "category": "brand_forbidden"},
    {"word": "co-working space",                 "language": "en", "severity": "high",   "category": "brand_forbidden"},
    {"word": "shared office",                    "language": "en", "severity": "high",   "category": "brand_forbidden"},
    {"word": "hot desk",                         "language": "en", "severity": "high",   "category": "brand_forbidden"},
    {"word": "take your business to the next level", "language": "en", "severity": "high", "category": "brand_forbidden"},
    {"word": "synergy",                          "language": "en", "severity": "medium", "category": "brand_forbidden"},
    {"word": "cutting-edge",                     "language": "en", "severity": "medium", "category": "brand_forbidden"},
    {"word": "all-in-one",                       "language": "en", "severity": "high",   "category": "brand_forbidden"},
    {"word": "unlock your potential",            "language": "en", "severity": "high",   "category": "brand_forbidden"},
    {"word": "dream big",                        "language": "en", "severity": "high",   "category": "brand_forbidden"},
    {"word": "best-in-class",                    "language": "en", "severity": "medium", "category": "brand_forbidden"},
    {"word": "world-class",                      "language": "en", "severity": "medium", "category": "brand_forbidden"},
    {"word": "premium",                          "language": "en", "severity": "low",    "category": "brand_forbidden"},
]
