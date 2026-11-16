"""
Module 3 - Lead Duplication Check.

Two leads are duplicates when they share a website domain, an email, a phone number
(last 9 digits) or the same normalised name in the same city.
"""
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

STOP_WORDS = {"the", "llc", "ltd", "inc", "co", "company", "pvt", "private", "limited", "fze", "fzco", "&", "and"}


def norm_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    u = url.strip().lower()
    if not u.startswith("http"):
        u = "http://" + u
    host = urlparse(u).netloc.split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    return host or None


def norm_email(email: Optional[str]) -> Optional[str]:
    return email.strip().lower() if email and "@" in email else None


def norm_phone(phone: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 7 else None


def norm_name(name: Optional[str], city: Optional[str] = None) -> Optional[str]:
    if not name:
        return None
    words = [w for w in re.sub(r"[^a-z0-9 ]", " ", name.lower()).split() if w not in STOP_WORDS]
    if not words:
        return None
    return " ".join(words) + "|" + (city or "").strip().lower()


def keys_for(lead: Dict[str, Any]) -> List[str]:
    keys = []
    d = norm_domain(lead.get("website"))
    if d:
        keys.append("domain:" + d)
    e = norm_email(lead.get("email"))
    if e:
        keys.append("email:" + e)
    p = norm_phone(lead.get("phone"))
    if p:
        keys.append("phone:" + p)
    n = norm_name(lead.get("business_name") or lead.get("name"), lead.get("city"))
    if n:
        keys.append("name:" + n)
    return keys


def find_matches(candidate: Dict[str, Any], existing: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ck = set(keys_for(candidate))
    out = []
    for lead in existing:
        shared = ck & set(keys_for(lead))
        if shared:
            out.append({"id": lead.get("id"), "business_name": lead.get("business_name"),
                        "matched_on": sorted(k.split(":", 1)[0] for k in shared)})
    return out


def find_duplicate_groups(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Union-find over shared keys -> groups of 2+ leads that are the same business."""
    parent = {i: i for i in range(len(leads))}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen: Dict[str, int] = {}
    reasons: Dict[int, set] = defaultdict(set)
    for i, lead in enumerate(leads):
        for k in keys_for(lead):
            if k in seen:
                a, b = find(seen[k]), find(i)
                if a != b:
                    parent[b] = a
                reasons[find(i)].add(k.split(":", 1)[0])
            else:
                seen[k] = i
    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(len(leads)):
        groups[find(i)].append(i)
    out = []
    for root, idx in groups.items():
        if len(idx) > 1:
            members = [leads[i] for i in idx]
            # suggest keeping the most complete record
            best = max(members, key=lambda m: sum(1 for f in ("website", "email", "phone", "address", "overall_score") if m.get(f)))
            all_reasons = set()
            for i in idx:
                all_reasons |= reasons.get(find(i), set())
            out.append({"keep_suggestion": best.get("id"), "matched_on": sorted(all_reasons) or ["name"],
                        "leads": members})
    return out

