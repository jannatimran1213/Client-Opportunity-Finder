"""
Module 8 - Industry-Specific Ready-Made Designs.

Each template is a full block list + theme the visual editor can open and customise.
Images use picsum.photos seeds so they always load; swap them for the client's own photos.
"""
import copy
import uuid
from typing import Any, Dict, List


def _b(t: str, **props) -> Dict[str, Any]:
    return {"type": t, "props": props}


def _img(seed: str, w: int = 1600, h: int = 900) -> str:
    return f"https://picsum.photos/seed/{seed}/{w}/{h}"


TEMPLATES: Dict[str, Dict[str, Any]] = {
    "restaurant": {"name": "Restaurant & Cafe", "industry": "restaurant", "kind": "page",
                   "theme": {"primary": "#C2410C", "font": "Playfair Display", "surface": "#FFF7ED"},
                   "blocks": [
                       _b("hero", heading="Fresh flavours, made with love", subheading="Family recipes, local ingredients and a table waiting for you.",
                          button_text="Reserve a table", button_link="#contact", image=_img("restaurant-hero"), align="center"),
                       _b("features", heading="Why guests love us", items=[
                           {"icon": "ðŸ½", "title": "Signature dishes", "text": "Chef-crafted plates you won't find anywhere else."},
                           {"icon": "ðŸšš", "title": "Order direct", "text": "Delivery and pickup without app commissions."},
                           {"icon": "â­", "title": "Rated 4.8", "text": "Hundreds of happy reviews from locals."}]),
                       _b("gallery", heading="From our kitchen", images=[_img("food1", 600, 400), _img("food2", 600, 400), _img("food3", 600, 400)]),
                       _b("testimonials", heading="What diners say", items=[{"quote": "Best dinner we've had in the city.", "author": "Sara K."},
                                                                             {"quote": "Warm staff and amazing food.", "author": "Omar R."}]),
                       _b("contact", heading="Book or order", phone="+971 50 000 0000", whatsapp="971500000000", address="Your street, Your city", show_form=True),
                       _b("map", address="Dubai Marina"), _b("footer", text="Â© Your Restaurant Â· Open daily 12pm-11pm")]},
    "dental": {"name": "Dental Clinic", "industry": "dental", "kind": "page",
               "theme": {"primary": "#0EA5E9", "font": "Inter", "surface": "#F0F9FF"},
               "blocks": [
                   _b("hero", heading="Gentle dental care for the whole family", subheading="Book online in 60 seconds. Same-week appointments available.",
                      button_text="Book appointment", button_link="#contact", image=_img("dental-hero"), align="center"),
                   _b("features", heading="Our treatments", items=[
                       {"icon": "ðŸ¦·", "title": "Check-ups & cleaning", "text": "Prevent problems before they start."},
                       {"icon": "âœ¨", "title": "Whitening", "text": "A brighter smile in one visit."},
                       {"icon": "ðŸ›¡", "title": "Implants & braces", "text": "Modern, comfortable treatment plans."}]),
                   _b("text", heading="Meet the dentist", body="<p>With over 10 years of experience, our team focuses on pain-free treatment and clear pricing.</p>"),
                   _b("pricing", heading="Transparent pricing", plans=[
                       {"name": "Check-up", "price": "AED 199", "features": ["Exam", "X-ray", "Cleaning"], "cta": "Book"},
                       {"name": "Whitening", "price": "AED 899", "features": ["1 session", "Take-home kit"], "cta": "Book"}]),
                   _b("testimonials", heading="Patient stories", items=[{"quote": "I used to fear dentists. Not anymore.", "author": "Ali M."}]),
                   _b("contact", heading="Book your visit", phone="+971 4 000 0000", email="hello@clinic.com", show_form=True),
                   _b("footer", text="Â© Your Dental Clinic")]},
    "real_estate": {"name": "Real Estate Agency", "industry": "real_estate", "kind": "page",
                    "theme": {"primary": "#0F766E", "font": "Poppins", "surface": "#F0FDFA"},
                    "blocks": [
                        _b("hero", heading="Find your next home", subheading="Hand-picked properties, honest advice and fast viewings.",
                           button_text="View listings", button_link="#listings", image=_img("realestate-hero"), align="center"),
                        _b("gallery", heading="Featured properties", images=[_img("house1", 600, 400), _img("house2", 600, 400), _img("house3", 600, 400)]),
                        _b("features", heading="How we help", items=[
                            {"icon": "ðŸ ", "title": "Buy", "text": "Access off-market deals."},
                            {"icon": "ðŸ’°", "title": "Sell", "text": "Free valuation in 24 hours."},
                            {"icon": "ðŸ”‘", "title": "Rent", "text": "Verified tenants and landlords."}]),
                        _b("cta", heading="Thinking of selling?", text="Get a free, no-obligation valuation.", button_text="Get valuation", button_link="#contact"),
                        _b("contact", heading="Talk to an agent", whatsapp="971500000000", email="agent@agency.com", show_form=True),
                        _b("footer", text="Â© Your Agency Â· RERA licensed")]},
    "salon": {"name": "Salon & Spa", "industry": "salon", "kind": "page",
              "theme": {"primary": "#DB2777", "font": "Lora", "surface": "#FDF2F8"},
              "blocks": [
                  _b("hero", heading="Look good. Feel better.", subheading="Hair, nails and spa treatments by expert stylists.",
                     button_text="Book now", button_link="#contact", image=_img("salon-hero"), align="center"),
                  _b("pricing", heading="Popular services", plans=[
                      {"name": "Cut & style", "price": "AED 150", "features": ["Wash", "Cut", "Blow-dry"], "cta": "Book"},
                      {"name": "Mani + Pedi", "price": "AED 180", "features": ["Gel polish", "Hand massage"], "cta": "Book"},
                      {"name": "Spa day", "price": "AED 450", "features": ["Massage", "Facial", "Steam"], "cta": "Book"}]),
                  _b("gallery", heading="Our work", images=[_img("salon1", 600, 400), _img("salon2", 600, 400), _img("salon3", 600, 400)]),
                  _b("contact", heading="Book your appointment", whatsapp="971500000000", phone="+971 50 000 0000", show_form=True),
                  _b("footer", text="Â© Your Salon")]},
    "gym": {"name": "Gym & Fitness", "industry": "gym", "kind": "page",
            "theme": {"primary": "#DC2626", "font": "Montserrat", "surface": "#FEF2F2", "background": "#ffffff"},
            "blocks": [
                _b("hero", heading="Stronger every week", subheading="Classes, coaching and a community that keeps you going.",
                   button_text="Claim free trial", button_link="#contact", image=_img("gym-hero"), align="center"),
                _b("features", heading="Train your way", items=[
                    {"icon": "ðŸ‹", "title": "Strength", "text": "Fully equipped free-weights zone."},
                    {"icon": "ðŸ”¥", "title": "HIIT classes", "text": "30-minute classes, 6 times a day."},
                    {"icon": "ðŸ§˜", "title": "Recovery", "text": "Yoga, stretching and sauna."}]),
                _b("pricing", heading="Memberships", plans=[
                    {"name": "Monthly", "price": "AED 299", "features": ["All classes", "Gym access"], "cta": "Join"},
                    {"name": "Annual", "price": "AED 2,999", "features": ["2 months free", "Personal plan"], "cta": "Join"}]),
                _b("cta", heading="Try us free for 3 days", text="No contract, no pressure.", button_text="Start trial", button_link="#contact"),
                _b("contact", heading="Get your free pass", show_form=True, whatsapp="971500000000"), _b("footer", text="Â© Your Gym")]},
    "law": {"name": "Law Firm", "industry": "legal", "kind": "page",
            "theme": {"primary": "#1E3A8A", "font": "Merriweather", "surface": "#EFF6FF"},
            "blocks": [
                _b("hero", heading="Clear legal advice you can trust", subheading="Corporate, family and property law. Free 15-minute consultation.",
                   button_text="Book consultation", button_link="#contact", align="center"),
                _b("features", heading="Practice areas", items=[
                    {"icon": "âš–", "title": "Corporate", "text": "Company setup, contracts, disputes."},
                    {"icon": "ðŸ‘ª", "title": "Family", "text": "Sensitive matters handled with care."},
                    {"icon": "ðŸ¢", "title": "Property", "text": "Due diligence and conveyancing."}]),
                _b("testimonials", heading="Client feedback", items=[{"quote": "Professional, fast and honest.", "author": "Business owner"}]),
                _b("contact", heading="Request a consultation", email="info@lawfirm.com", phone="+971 4 000 0000", show_form=True),
                _b("footer", text="Â© Your Law Firm")]},
    "accounting": {"name": "Accounting & Tax Firm", "industry": "accounting", "kind": "page",
                   "theme": {"primary": "#047857", "font": "Inter", "surface": "#ECFDF5"},
                   "blocks": [
                       _b("hero", heading="Bookkeeping, VAT & Corporate Tax made simple", subheading="Stay compliant and focus on growing your business.",
                          button_text="Free consultation", button_link="#contact", align="center"),
                       _b("features", heading="Services", items=[
                           {"icon": "ðŸ“’", "title": "Bookkeeping", "text": "Monthly books and management reports."},
                           {"icon": "ðŸ§¾", "title": "VAT & Corporate Tax", "text": "Registration, filing and advisory."},
                           {"icon": "ðŸ“Š", "title": "CFO services", "text": "Budgets, cash-flow and strategy."}]),
                       _b("cta", heading="Deadline coming up?", text="We'll get your filing done on time.", button_text="Talk to us", button_link="#contact"),
                       _b("contact", heading="Book a free call", email="hello@firm.com", whatsapp="971500000000", show_form=True),
                       _b("footer", text="Â© Your Firm")]},
    "home_services": {"name": "Plumber / Contractor", "industry": "home_services", "kind": "page",
                      "theme": {"primary": "#EA580C", "font": "Roboto", "surface": "#FFF7ED"},
                      "blocks": [
                          _b("hero", heading="Fast, reliable repairs - same day", subheading="Licensed technicians. Upfront prices. 24/7 emergency line.",
                             button_text="Call now", button_link="tel:+971500000000", image=_img("tools-hero"), align="center"),
                          _b("features", heading="What we fix", items=[
                              {"icon": "ðŸ”§", "title": "Plumbing", "text": "Leaks, blockages, water heaters."},
                              {"icon": "ðŸ’¡", "title": "Electrical", "text": "Wiring, lighting, panels."},
                              {"icon": "â„", "title": "AC", "text": "Service, gas refill, repairs."}]),
                          _b("testimonials", heading="Reviews", items=[{"quote": "Arrived in 40 minutes and fixed it fast.", "author": "Villa owner"}]),
                          _b("contact", heading="Get a free quote", phone="+971 50 000 0000", whatsapp="971500000000", show_form=True),
                          _b("footer", text="Â© Your Company")]},
    "agency_email": {"name": "Cold outreach email (audit offer)", "industry": "generic", "kind": "email",
                     "theme": {"primary": "#6D5DF6"},
                     "blocks": [
                         _b("hero", heading="3 quick wins for your website", subheading="We ran a free audit of your site. Here is what we found.", button_text="See the full report", button_link="https://example.com/report"),
                         _b("features", heading="Highlights", items=[
                             {"icon": "âš¡", "title": "Speed", "text": "Your homepage loads in 4.2s; we can get it under 2s."},
                             {"icon": "ðŸ“±", "title": "Mobile", "text": "Buttons are hard to tap on phones."},
                             {"icon": "ðŸ”’", "title": "Security", "text": "Two missing security headers."}]),
                         _b("button", text="Book a 15-minute call", link="https://example.com/book", align="center"),
                         _b("footer", text="You received this because your business is listed publicly. Reply STOP to opt out.")]},
    "newsletter_email": {"name": "Newsletter email", "industry": "generic", "kind": "email", "theme": {"primary": "#0EA5E9"},
                         "blocks": [
                             _b("hero", heading="This month's update", subheading="News, tips and offers for our clients.", button_text="", button_link="#"),
                             _b("image", src=_img("newsletter", 1200, 500), alt="", caption=""),
                             _b("text", heading="What's new", body="<p>Share your latest news here.</p>"),
                             _b("cta", heading="Special offer", text="20% off for the next 7 days.", button_text="Claim offer", button_link="https://example.com"),
                             _b("footer", text="Â© Your Company Â· Unsubscribe")]},
}


def list_templates() -> List[Dict[str, Any]]:
    return [{"key": k, "name": v["name"], "industry": v["industry"], "kind": v["kind"], "theme": v["theme"],
             "block_count": len(v["blocks"]), "preview_image": next((b["props"].get("image") for b in v["blocks"] if b["props"].get("image")), None)}
            for k, v in TEMPLATES.items()]


def instantiate(key: str) -> Dict[str, Any]:
    tpl = TEMPLATES.get(key)
    if not tpl:
        raise KeyError(key)
    blocks = copy.deepcopy(tpl["blocks"])
    for b in blocks:
        b["id"] = uuid.uuid4().hex[:10]
    return {"blocks": blocks, "theme": copy.deepcopy(tpl["theme"]), "kind": tpl["kind"], "name": tpl["name"]}

