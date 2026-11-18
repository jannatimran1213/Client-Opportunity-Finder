"""
Module 5 - Industry-Specific Content packs used by the copywriter (LLM prompt context + template fallback).
"""
INDUSTRIES = {
    "restaurant": {"label": "Restaurants & Cafes", "keywords": ["restaurant", "cafe", "food", "bakery", "fast_food", "bar"],
                   "pains": ["empty tables on weekdays", "high commission on delivery apps", "menus that are hard to read on phones"],
                   "offers": ["a mobile-first menu and online ordering page", "Google reviews and local SEO", "a WhatsApp ordering button"],
                   "outcome": "more direct orders without the delivery-app commission", "cta": "Would a 10-minute call this week be useful?"},
    "dental": {"label": "Dental & Clinics", "keywords": ["dentist", "dental", "clinic", "doctor", "hospital", "pharmacy"],
               "pains": ["patients who can't book online", "slow pages that lose mobile visitors", "few recent Google reviews"],
               "offers": ["24/7 online appointment booking", "a fast, trust-building clinic website", "automated review requests"],
               "outcome": "a fuller appointment book every week", "cta": "Can I send you a short plan for your clinic?"},
    "real_estate": {"label": "Real Estate", "keywords": ["real_estate", "estate_agent", "property", "realtor"],
                    "pains": ["listings buried on portals", "leads that go cold after the first enquiry", "no follow-up system"],
                    "offers": ["a listings site that captures buyer details", "instant WhatsApp lead alerts", "automated follow-ups"],
                    "outcome": "more qualified buyer and seller enquiries", "cta": "Open to a quick call on Thursday?"},
    "salon": {"label": "Salons & Spas", "keywords": ["salon", "hairdresser", "beauty", "spa", "barber", "nail"],
              "pains": ["no-shows", "booking only by phone", "Instagram followers that never book"],
              "offers": ["online booking with reminders", "a booking link in your Instagram bio", "a loyalty offer page"],
              "outcome": "fewer no-shows and a fuller calendar", "cta": "Shall I show you how it would look for your salon?"},
    "gym": {"label": "Gyms & Fitness", "keywords": ["gym", "fitness", "fitness_centre", "yoga", "sports_centre"],
            "pains": ["seasonal sign-up dips", "trial visitors who never convert", "no online membership sign-up"],
            "offers": ["a free-trial landing page", "class schedules with online booking", "automated trial follow-ups"],
            "outcome": "more trials turning into paying members", "cta": "Worth a quick chat this week?"},
    "legal": {"label": "Law Firms", "keywords": ["lawyer", "law", "legal", "attorney", "notary"],
              "pains": ["low visibility for practice-area searches", "contact forms nobody answers fast", "dated website design"],
              "offers": ["practice-area pages that rank locally", "an intake form that books consultations", "a modern, credible site"],
              "outcome": "more consultation requests from the right clients", "cta": "Could we schedule 15 minutes to discuss?"},
    "accounting": {"label": "Accounting, Tax & Consulting", "keywords": ["accountant", "accounting", "tax", "consulting", "audit", "vat"],
                   "pains": ["clients who only find you by referral", "deadline rushes", "no way to book a consultation online"],
                   "offers": ["service pages for VAT, corporate tax and bookkeeping", "an online consultation booking flow", "a lead magnet like a tax-deadline checklist"],
                   "outcome": "a steady flow of new business clients", "cta": "Would you be open to a short call?"},
    "home_services": {"label": "Plumbers, Electricians & Contractors", "keywords": ["plumber", "electrician", "contractor", "roofer", "hvac", "construction", "builder"],
                      "pains": ["missed calls while on a job", "relying on word of mouth", "no reviews online"],
                      "offers": ["a click-to-call quote page", "Google Business Profile optimisation", "automatic review requests after each job"],
                      "outcome": "more booked jobs from local searches", "cta": "Can I send a quick example for your business?"},
    "hotel": {"label": "Hotels & Travel", "keywords": ["hotel", "guest_house", "hostel", "travel_agency", "resort"],
              "pains": ["OTA commissions", "no direct-booking incentive", "slow mobile booking"],
              "offers": ["a direct-booking engine on your site", "a best-rate guarantee page", "abandoned-booking follow-ups"],
              "outcome": "more direct bookings at a better margin", "cta": "Open to a quick call to explore it?"},
    "retail": {"label": "Retail & E-commerce", "keywords": ["shop", "store", "boutique", "clothes", "supermarket", "retail"],
               "pains": ["foot traffic only", "no online store", "abandoned carts"],
               "offers": ["an online store with WhatsApp checkout", "local inventory ads", "cart-recovery messages"],
               "outcome": "online sales on top of walk-in customers", "cta": "Shall I share a few ideas for your store?"},
    "education": {"label": "Schools & Training", "keywords": ["school", "college", "academy", "training", "tuition", "kindergarten"],
                  "pains": ["admission enquiries handled by phone", "no course pages", "parents comparing on mobile"],
                  "offers": ["an admissions landing page with online forms", "course pages that rank", "WhatsApp enquiry replies"],
                  "outcome": "more admissions enquiries each intake", "cta": "Could we talk for 10 minutes this week?"},
    "automotive": {"label": "Automotive", "keywords": ["car_repair", "car_dealer", "garage", "auto", "car_wash"],
                   "pains": ["customers can't book a service slot online", "few reviews", "no pricing transparency"],
                   "offers": ["online service booking", "a transparent price list page", "review and reminder automation"],
                   "outcome": "a full workshop schedule", "cta": "Worth a quick call?"},
    "generic": {"label": "Any Business", "keywords": [],
                "pains": ["a website that doesn't turn visitors into enquiries", "slow mobile pages", "no follow-up system"],
                "offers": ["a fast, mobile-friendly website", "lead capture and follow-up automation", "local SEO"],
                "outcome": "more enquiries from people already looking for you", "cta": "Would a short call this week be helpful?"},
}

CONTENT_TYPES = {
    "cold_email": "Cold outreach email",
    "follow_up": "Follow-up email",
    "linkedin_note": "LinkedIn connection note (max 300 characters)",
    "whatsapp": "WhatsApp intro message",
    "landing_copy": "Landing page copy (headline, sub-headline, 3 benefits, CTA)",
    "social_post": "Social media post",
}


def detect_industry(category: str = "", name: str = "") -> str:
    text = f"{category or ''} {name or ''}".lower()
    for key, pack in INDUSTRIES.items():
        if any(k in text for k in pack["keywords"]):
            return key
    return "generic"


def get_pack(industry: str) -> dict:
    return INDUSTRIES.get(industry) or INDUSTRIES["generic"]

