"""
End-to-end smoke test for the 32 features. Run against a running backend:

    uvicorn app.main:app --port 8000          # in one terminal
    python scripts/smoke_test_features.py     # in another  (BASE=http://localhost:8000 by default)

Uses only offline-safe paths by default (no paid APIs needed). Set SMOKE_NETWORK=1 to also hit
external websites (finder search, scraping, advanced audit, benchmarking).
"""
import os
import sys
import time
import uuid

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BASE = os.getenv("BASE", "http://localhost:8000").rstrip("/") + "/api/v1"
NET = os.getenv("SMOKE_NETWORK") == "1"
ok_count, fail = 0, []


def check(name, cond, info=""):
    global ok_count
    if cond:
        ok_count += 1
        print(f"  PASS  {name}")
    else:
        fail.append(name)
        print(f"  FAIL  {name}  {str(info)[:300]}")


def main():
    c = httpx.Client(timeout=120)
    email = f"demo_{uuid.uuid4().hex[:6]}@example.org"
    print("== 1. Sign Up & SaaS Access")
    r = c.post(f"{BASE}/auth/signup", json={"full_name": "Demo Owner", "email": email, "password": "Passw0rd!x",
                                            "workspace_name": "Demo Agency"})
    check("Create an Account", r.status_code == 200 and r.json().get("token"), r.text)
    tok = r.json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    ws = c.get(f"{BASE}/workspaces", headers=H).json()["workspaces"]
    check("Multi-Tenant Workspace (auto-created)", len(ws) == 1 and ws[0]["role"] == "owner", ws)
    H["X-Workspace-Id"] = ws[0]["id"]
    sub = c.get(f"{BASE}/billing/subscription", headers=H).json()
    check("Subscription Engine (Basic trial + limits)", sub["subscription"]["plan"] == "basic" and sub["limits"]["leads"] > 0, sub)
    up = c.post(f"{BASE}/billing/checkout", headers=H, json={"plan": "pro", "interval": "yearly"}).json()
    check("Subscription upgrade (test mode)", up.get("activated") and up["subscription"]["plan"] == "pro", up)
    roles = c.get(f"{BASE}/workspaces/roles", headers=H).json()
    check("RBAC matrix", "viewer" in roles["matrix"] and not roles["matrix"]["viewer"]["leads:write"], roles)
    # second user as viewer -> must be blocked from writing
    v_email = f"viewer_{uuid.uuid4().hex[:6]}@example.org"
    inv = c.post(f"{BASE}/workspaces/members/invite", headers=H, json={"email": v_email, "role": "viewer"}).json()
    token = inv["invite_link"].split("invite=")[1].split("&")[0]
    rv = c.post(f"{BASE}/auth/signup", json={"full_name": "Viewer", "email": v_email, "password": "Passw0rd!x", "invite_token": token}).json()
    HV = {"Authorization": f"Bearer {rv['token']}", "X-Workspace-Id": ws[0]["id"]}
    blocked = c.post(f"{BASE}/leads/save", headers=HV, json={"businesses": [{"business_name": "X"}]})
    check("RBAC: viewer cannot write", blocked.status_code == 403, blocked.text)
    other = c.post(f"{BASE}/auth/signup", json={"full_name": "Other", "email": f"o_{uuid.uuid4().hex[:6]}@example.org", "password": "Passw0rd!x"}).json()
    HO = {"Authorization": f"Bearer {other['token']}", "X-Workspace-Id": ws[0]["id"]}
    check("Tenant isolation: outsider blocked", c.get(f"{BASE}/leads", headers=HO).status_code == 403)

    print("== 2. Custom Business Finder")
    html = ('<html><head><title>Smile Dental</title><script type="application/ld+json">{"@type":"Dentist","name":"Smile Dental",'
            '"telephone":"+971 4 123 4567","address":{"streetAddress":"1 Beach Rd","addressLocality":"Dubai"}}</script></head>'
            '<body>Email us: info@smiledental.ae <a href="https://wa.me/971501234567">WhatsApp</a> '
            '<a href="https://www.instagram.com/smiledental">IG</a> <a href="/contact">Contact</a></body></html>')
    pr = c.post(f"{BASE}/finder/parse", headers=H, json={"html": html, "url": "https://smiledental.ae"}).json()
    check("Data Parser & Extraction", "info@smiledental.ae" in pr["emails"] and pr["whatsapp"] and pr["business"].get("city") == "Dubai", pr)
    check("Business types endpoint", c.get(f"{BASE}/finder/business-types", headers=H).status_code == 200)
    if NET:
        s = c.post(f"{BASE}/finder/search", headers=H, json={"business_type": "dentist", "city": "Dubai", "country": "UAE", "max_results": 10})
        check("Search by Type & City", s.status_code == 200 and s.json()["result_count"] >= 0, s.text)
        sc = c.post(f"{BASE}/finder/scrape", headers=H, json={"url": "https://example.com", "max_pages": 2})
        check("Proprietary Web Scraper", sc.status_code == 200, sc.text)
        d = c.post(f"{BASE}/finder/discover", headers=H, json={"businesses": [{"business_name": "Burj Al Arab", "city": "Dubai"}]})
        check("Find Websites Automatically", d.status_code == 200, d.text)

    print("== 3. Lead Management")
    saved = c.post(f"{BASE}/leads/save", headers=H, json={"businesses": [
        {"business_name": "Smile Dental", "website": "https://smiledental.ae", "email": "info@smiledental.ae", "phone": "+97141234567", "city": "Dubai", "category": "dentist", "country": "UAE"},
        {"business_name": "Blue Cafe", "website": "https://bluecafe.example", "email": "hello@bluecafe.example", "phone": "0501112222", "city": "Dubai", "category": "cafe", "country": "UAE"},
        {"business_name": "Smile Dental LLC", "website": "http://www.smiledental.ae/", "city": "Dubai"},
    ]}).json()
    check("Save Promising Businesses + Duplication Check on save", saved["saved"] == 2 and saved["skipped_duplicates"] == 1, saved)
    leads = c.get(f"{BASE}/leads", headers=H).json()["leads"]
    lid = {l["business_name"]: l["id"] for l in leads}
    lst = c.post(f"{BASE}/leads/lists", headers=H, json={"name": "Dubai hot leads"}).json()
    c.post(f"{BASE}/leads/lists/{lst['id']}/items", headers=H, json={"business_ids": list(lid.values())})
    upd = c.put(f"{BASE}/leads/{lid['Blue Cafe']}", headers=H, json={"status": "contacted", "tags": ["vip"], "notes": "Owner is Ahmed"}).json()
    in_list = c.get(f"{BASE}/leads", headers=H, params={"list_id": lst["id"]}).json()["total"]
    check("Edit and Organize Lists", upd["status"] == "contacted" and "vip" in upd["tags"] and in_list == 2, upd)
    val = c.post(f"{BASE}/leads/validate", headers=H, json={"all": True, "check_website": NET, "check_mx": NET}).json()
    check("Validation Filter", val["summary"]["checked"] == 2 and val["results"][0]["phone"]["status"] in ("valid", "invalid"), val)
    c.post(f"{BASE}/leads", headers=H)  # no-op
    dup = c.post(f"{BASE}/leads/check-duplicate", headers=H, json={"business_name": "Blue Cafe", "city": "Dubai"}).json()
    check("Lead Duplication Check", dup["is_duplicate"], dup)

    print("== 4. Advanced Audit")
    if NET:
        a = c.post(f"{BASE}/advanced-audits/run", headers=H, json={"url": "https://example.com"})
        j = a.json() if a.status_code == 200 else {}
        check("Speed & Security Audit", a.status_code == 200 and "security" in j and "speed" in j, a.text)
        check("Tech Stack Detection", isinstance(j.get("tech_stack"), list))
        check("Mobile Friendliness Score", j.get("mobile", {}).get("score") is not None)
        check("SEO indexing checks", j.get("seo", {}).get("checks"))
        check("Trust & Conversion Leak Detector", "leaks" in j.get("trust", {}))
        b = c.post(f"{BASE}/advanced-audits/benchmark", headers=H, json={"target_url": "https://example.com", "competitor_urls": ["https://example.org"]})
        check("Competitor Benchmarking", b.status_code == 200 and len(b.json()["ranking"]) == 2, b.text)
    else:
        print("  (skipped - set SMOKE_NETWORK=1)")

    print("== 5. AI Copywriter")
    ib = c.post(f"{BASE}/copywriter/icebreakers", headers=H, json={"business_id": lid["Smile Dental"]}).json()
    check("Personalized Icebreakers", len(ib["icebreakers"]) >= 1, ib)
    bulk = c.post(f"{BASE}/copywriter/bulk", headers=H, json={"list_id": lst["id"]}).json()
    check("Bulk Email Generation", bulk["count"] == 2 and bulk["drafts"][0]["body"], bulk)
    rep = c.post(f"{BASE}/copywriter/reply", headers=H, json={"message": "Sounds good, how much does it cost?", "business_id": lid["Blue Cafe"]}).json()
    check("Dynamic Reply Assistant", rep["intent"] == "pricing" and rep["suggested_replies"], rep)
    ic = c.post(f"{BASE}/copywriter/industry-content", headers=H, json={"industry": "dental", "content_type": "landing_copy"}).json()
    check("Industry-Specific Content", "HEADLINE" in ic["body"] or ic["source"] == "llm", ic)

    print("== 6. Multi-Channel Send")
    st = c.get(f"{BASE}/channels/status", headers=H).json()
    check("Connect Gmail & Business Email (status + endpoints)", "email" in st and c.get(f"{BASE}/email-accounts/smtp-presets", headers=H).status_code == 200, st)
    li = c.post(f"{BASE}/channels/linkedin/tasks", headers=H, json={"business_id": lid["Blue Cafe"], "action": "connect"}).json()
    done = c.put(f"{BASE}/channels/linkedin/tasks/{li['id']}", headers=H, json={"status": "done"}).json()
    check("LinkedIn Automation (assisted queue)", li["message"] and done["status"] == "done", li)
    wa = c.post(f"{BASE}/channels/whatsapp/send", headers=H, json={"to": "+971501112222", "body": "Hello from the demo"}).json()
    check("WhatsApp API Integration (simulated without keys)", wa.get("success") and (wa.get("simulated") or wa.get("message_id")), wa)
    from app.services.channels import tracking as tr
    tok_ = "smoketok" + uuid.uuid4().hex[:6]
    # insert a tracked email directly through the public flow is not possible without SMTP, so verify the engine:
    html = tr.instrument_html('<p>Hi <a href="https://example.com/offer">offer</a></p>', tok_)
    check("Tracking Pixel Engine (instrumentation)", "/api/v1/track/o/" in html and "/api/v1/track/c/" in html, html)
    px = c.get(f"{BASE}/track/o/{tok_}.gif")
    check("Tracking pixel endpoint returns GIF", px.status_code == 200 and px.headers["content-type"] == "image/gif")
    bad = c.get(f"{BASE}/track/c/{tok_}", params={"u": "https://evil.example", "s": "bad"})
    check("Click redirect rejects unsigned links", bad.status_code == 400)

    print("== 7. Schedule Meeting")
    from datetime import datetime, timedelta, timezone
    start = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
    m = c.post(f"{BASE}/meetings", headers=H, json={"title": "Discovery call - Smile Dental", "start_at": start,
                                                    "business_id": lid["Smile Dental"], "meeting_link": "https://meet.google.com/abc",
                                                    "reminders": [{"minutes_before": 5, "channel": "in_app"}]}).json()
    check("Add Meeting Date & Time", m.get("id") and m["status"] == "scheduled", m)
    check("Set Reminders", len(m["reminders"]) == 1, m)
    ics = c.get(f"{BASE}/meetings/{m['id']}/ics", headers=H)
    check("Calendar (.ics) export", "BEGIN:VCALENDAR" in ics.text)
    c.post(f"{BASE}/meetings/reminders/run-due", headers=H)
    notes = c.get(f"{BASE}/notifications", headers=H).json()
    check("Notifications", notes["unread"] >= 1, notes)
    comp = c.post(f"{BASE}/meetings/{m['id']}/complete", headers=H, json={"outcome": "Interested in website", "next_steps": ["Send proposal"], "follow_up_in_days": 2}).json()
    fus = c.get(f"{BASE}/follow-ups", headers=H).json()
    check("Follow-up Tracker", comp["follow_up_id"] and fus["counts"]["upcoming"] >= 1, fus)
    ns = c.get(f"{BASE}/next-steps", headers=H).json()["next_steps"]
    ns2 = c.post(f"{BASE}/next-steps", headers=H, json={"title": "Sign contract", "business_id": lid["Smile Dental"], "stage": "contract"}).json()
    check("Set Next Steps", any(s["title"] == "Send proposal" for s in ns) and ns2["stage"] == "contract", ns)

    print("== 8. Drag-and-Drop Builder")
    tpls = c.get(f"{BASE}/builder/templates", headers=H).json()["templates"]
    check("Industry-Specific Ready-Made Designs", len(tpls) >= 8, tpls)
    pg = c.post(f"{BASE}/builder/pages", headers=H, json={"template_key": "dental", "business_id": lid["Smile Dental"]}).json()
    blocks = pg["blocks"] + [{"type": "button", "props": {"text": "Call us", "link": "tel:+97141234567"}}]
    blocks[0], blocks[1] = blocks[1], blocks[0]  # simulate a drag-and-drop reorder
    upd = c.put(f"{BASE}/builder/pages/{pg['id']}", headers=H, json={"blocks": blocks, "theme": {"primary": "#ff0055"}}).json()
    prev = c.post(f"{BASE}/builder/render", headers=H, json={"blocks": blocks, "theme": {"primary": "#ff0055"}})
    check("Visual Editor (save blocks + live render)", upd["block_count"] == len(blocks) and "#ff0055" in prev.text, upd)
    subname = "smile-" + uuid.uuid4().hex[:5]
    pub = c.post(f"{BASE}/builder/pages/{pg['id']}/publish", headers=H, json={"subdomain": subname}).json()
    live = c.get(BASE.replace("/api/v1", "") + f"/sites/{subname}")
    live_host = c.get(BASE.replace("/api/v1", "") + "/", headers={"Host": f"{subname}.sites.localtest.me"})
    check("Live Subdomain Hosting", pub["published"] and live.status_code == 200 and "Smile Dental" in live.text, pub)
    ex = c.get(f"{BASE}/builder/pages/{pg['id']}/export", headers=H)
    check("Export Project (Code)", ex.status_code == 200 and ex.headers["content-type"] == "application/zip" and ex.content[:2] == b"PK")

    print("== Extras (proposal: Celery jobs, calendar slots, timeline, smart no-reply reminders)")
    job = c.post(f"{BASE}/jobs", headers=H, json={"kind": "validate_leads", "payload": {"all": True, "check_website": False, "check_mx": False}}).json()
    for _ in range(60):
        jj = c.get(f"{BASE}/jobs/{job['id']}", headers=H).json()
        if jj["status"] in ("completed", "failed"):
            break
        time.sleep(1)
    check(f"Background job ({jj.get('runner')})", jj["status"] == "completed", jj)
    from datetime import date as _d
    sl = c.get(f"{BASE}/meetings/slots", headers=H, params={"day": (_d.today() + timedelta(days=1)).isoformat(), "duration_minutes": 30}).json()
    check("Calendar slots", len(sl["slots"]) > 0, sl)
    tl = c.get(f"{BASE}/meetings/timeline/{lid['Blue Cafe']}", headers=H).json()
    check("Discussion timeline", len(tl["events"]) >= 1, tl)
    rd = c.post(f"{BASE}/meetings/reminders/run-due", headers=H).json()
    check("Smart reminders run", "no_reply_alerts" in rd, rd)

    print(f"\n{ok_count} passed, {len(fail)} failed")
    if fail:
        print("Failed:", ", ".join(fail))
        sys.exit(1)


if __name__ == "__main__":
    main()
