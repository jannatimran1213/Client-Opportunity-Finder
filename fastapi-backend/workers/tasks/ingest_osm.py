"""Celery task: OpenStreetMap business search by type & city (Overpass)."""
from app.core.celery_app import celery_app


@celery_app.task(name="workers.tasks.ingest_osm.search_businesses")
def search_businesses(business_type: str, city: str, country: str = "", radius_meters: int = 8000) -> dict:
    from app.services.osm.osm_service import OSMService
    return OSMService().search_businesses(business_type=business_type, city=city, country=country, radius_meters=radius_meters)


@celery_app.task(name="workers.tasks.ingest_osm.scrape_website")
def scrape_website(url: str, max_pages: int = 10) -> dict:
    """Proprietary crawler: fast httpx crawl with a Playwright (headless Chromium) fallback for JS-heavy sites."""
    import asyncio
    from app.services.scraping.website_scraper import scrape_website_for_contacts
    contacts = asyncio.run(scrape_website_for_contacts(url, max_pages=max_pages))
    return contacts.to_dict() if contacts else {}
