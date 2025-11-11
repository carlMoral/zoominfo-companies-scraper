import json
import logging
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .data_utils import (
    clean_text,
    extract_currency_amount,
    merge_dicts,
    normalize_list,
    parse_int_safe,
    safe_get,
)

logger = logging.getLogger(__name__)

@dataclass
class LeadershipProfile:
    name: Optional[str]
    title: Optional[str]
    url: Optional[str]

@dataclass
class TechStackItem:
    company_name: Optional[str]
    tech_name: Optional[str]

@dataclass
class NewsItem:
    title: Optional[str]
    url: Optional[str]

@dataclass
class CompanyRecord:
    url: str
    id: Optional[str]
    name: Optional[str]
    description: Optional[str]
    revenue: Optional[float]
    revenue_currency: Optional[str]
    stock_symbol: Optional[str]
    website: Optional[str]
    employees: Optional[int]
    industry: List[str]
    headquarters: Optional[str]
    phone_number: Optional[str]
    total_funding_amount: Optional[float]
    most_recent_funding_amount: Optional[float]
    funding_currency: Optional[str]
    funding_rounds: Optional[int]
    leadership: List[LeadershipProfile]
    popular_searches: List[str]
    business_classification_codes: List[str]
    total_employees: Optional[int]
    c_level_employees: Optional[int]
    vp_level_employees: Optional[int]
    director_level_employees: Optional[int]
    manager_level_employees: Optional[int]
    non_manager_employees: Optional[int]
    top_contacts: Optional[int]
    org_chart: List[Dict[str, Any]]
    social_media: List[str]
    ceo_rating: Optional[float]
    enps_score: Optional[float]
    similar_companies: List[str]
    email_formats: List[str]
    products_owned: List[str]
    tech_stack: List[TechStackItem]
    recent_scoops: List[Dict[str, Any]]
    news_and_media: List[NewsItem]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Convert nested dataclasses
        data["leadership"] = [asdict(item) for item in self.leadership]
        data["tech_stack"] = [asdict(item) for item in self.tech_stack]
        data["news_and_media"] = [asdict(item) for item in self.news_and_media]
        return data

class ZoomInfoCompanyParser:
    """
    Parser responsible for extracting structured company data from a ZoomInfo company page HTML.
    The implementation uses a combination of JSON-LD, meta tags, and heuristic CSS selectors.
    """

    def parse_company(self, html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        logger.debug("Parsing company page for %s", url)

        ld_json_data = self._extract_ld_json(soup)
        logger.debug("Extracted JSON-LD payload: %s", ld_json_data)

        base_data = self._parse_from_ld_json(ld_json_data)
        fallback_data = self._parse_html_fallbacks(soup)

        merged = merge_dicts(base_data, fallback_data)

        company = CompanyRecord(
            url=url,
            id=self._extract_company_id(url, ld_json_data),
            name=clean_text(merged.get("name")),
            description=clean_text(merged.get("description")),
            revenue=merged.get("revenue"),
            revenue_currency=merged.get("revenue_currency"),
            stock_symbol=clean_text(merged.get("stock_symbol")),
            website=clean_text(merged.get("website")),
            employees=parse_int_safe(merged.get("employees")),
            industry=[i for i in normalize_list(merged.get("industry")) if i],
            headquarters=clean_text(merged.get("headquarters")),
            phone_number=clean_text(merged.get("phone_number")),
            total_funding_amount=merged.get("total_funding_amount"),
            most_recent_funding_amount=merged.get("most_recent_funding_amount"),
            funding_currency=merged.get("funding_currency"),
            funding_rounds=parse_int_safe(merged.get("funding_rounds")),
            leadership=self._parse_leadership(merged.get("leadership")),
            popular_searches=[
                s for s in normalize_list(merged.get("popular_searches")) if s
            ],
            business_classification_codes=[
                s
                for s in normalize_list(
                    merged.get("business_classification_codes")
                )
                if s
            ],
            total_employees=parse_int_safe(
                merged.get("total_employees", merged.get("employees"))
            ),
            c_level_employees=parse_int_safe(merged.get("c_level_employees")),
            vp_level_employees=parse_int_safe(merged.get("vp_level_employees")),
            director_level_employees=parse_int_safe(
                merged.get("director_level_employees")
            ),
            manager_level_employees=parse_int_safe(
                merged.get("manager_level_employees")
            ),
            non_manager_employees=parse_int_safe(
                merged.get("non_manager_employees")
            ),
            top_contacts=parse_int_safe(merged.get("top_contacts")),
            org_chart=normalize_list(merged.get("org_chart")),
            social_media=[
                s for s in normalize_list(merged.get("social_media")) if s
            ],
            ceo_rating=self._parse_float_or_none(merged.get("ceo_rating")),
            enps_score=self._parse_float_or_none(
                merged.get("enps_score") or merged.get("enps score")
            ),
            similar_companies=[
                s for s in normalize_list(merged.get("similar_companies")) if s
            ],
            email_formats=[
                s for s in normalize_list(merged.get("email_formats")) if s
            ],
            products_owned=[
                s for s in normalize_list(merged.get("products_owned")) if s
            ],
            tech_stack=self._parse_tech_stack(merged.get("tech_stack")),
            recent_scoops=normalize_list(merged.get("recent_scoops")),
            news_and_media=self._parse_news_items(merged.get("news_and_media")),
        )

        return company.to_dict()

    # JSON-LD and HTML helpers

    def _extract_ld_json(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract the most relevant JSON-LD organization payload, if present.
        """
        scripts = soup.find_all("script", type="application/ld+json")
        best: Dict[str, Any] = {}
        for script in scripts:
            try:
                data = json.loads(script.string or "")
            except Exception:  # noqa: BLE001
                continue

            if isinstance(data, list):
                candidates = data
            else:
                candidates = [data]

            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                if candidate.get("@type") in ("Organization", "Corporation"):
                    best = candidate
        return best

    def _parse_from_ld_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map JSON-LD fields into our internal model keys.
        """
        if not data:
            return {}

        result: Dict[str, Any] = {}
        result["name"] = data.get("name")
        result["description"] = data.get("description")
        result["website"] = data.get("url") or data.get("sameAs")

        address = safe_get(data, "address")
        if isinstance(address, dict):
            parts = [
                address.get("streetAddress"),
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("postalCode"),
                address.get("addressCountry"),
            ]
            result["headquarters"] = clean_text(
                ", ".join([p for p in parts if p])
            )

        result["phone_number"] = data.get("telephone")
        result["industry"] = normalize_list(data.get("industry") or [])

        result["social_media"] = []
        for link in normalize_list(data.get("sameAs") or []):
            if isinstance(link, str):
                result["social_media"].append(link)

        # Revenue and employees may appear under 'employee' or custom props
        employees = safe_get(data, "numberOfEmployees") or data.get(
            "employees"
        )
        result["employees"] = parse_int_safe(employees)

        # Funding and revenue might be encoded in additionalProperty or similar structures
        additional_props = data.get("additionalProperty")
        if isinstance(additional_props, list):
            for prop in additional_props:
                name = prop.get("name")
                val = prop.get("value")
                if not name:
                    continue
                lname = str(name).lower()
                if "revenue" in lname:
                    amount, currency = extract_currency_amount(str(val))
                    result["revenue"] = amount
                    result["revenue_currency"] = currency
                if "funding" in lname:
                    amount, currency = extract_currency_amount(str(val))
                    result["total_funding_amount"] = amount
                    result["funding_currency"] = currency

        return result

    def _parse_html_fallbacks(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Fallback extraction using meta tags and heuristic selectors.
        This keeps the scraper functional even if JSON-LD is missing.
        """
        result: Dict[str, Any] = {}

        # Title / name
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            result["name"] = og_title["content"]

        # Description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            result["description"] = meta_desc["content"]

        # Website from links
        website_link = soup.find("a", href=re.compile(r"^https?://", re.I))
        if website_link and website_link.get("href"):
            result["website"] = website_link["href"]

        # Phone number heuristic
        phone = soup.find(string=re.compile(r"\+?\d[\d\s().-]{6,}"))
        if phone:
            result["phone_number"] = phone.strip()

        # Industry from labels or chips
        industry_tags = soup.select("[data-qa='industry'], .industry, .industries")
        industries: List[str] = []
        for tag in industry_tags:
            text = tag.get_text(" ", strip=True)
            if text:
                industries.append(text)
        if industries:
            result["industry"] = industries

        # Headquarters / address
        address_selectors = [
            "[data-qa='address']",
            ".address",
            ".hq",
            ".headquarters",
        ]
        for sel in address_selectors:
            node = soup.select_one(sel)
            if node:
                result["headquarters"] = node.get_text(" ", strip=True)
                break

        # Employees
        employees_text_nodes = soup.find_all(
            string=re.compile(r"(employees|employee count)", re.I)
        )
        for node in employees_text_nodes:
            m = re.search(r"([\d,]+)", node)
            if m:
                result["employees"] = parse_int_safe(m.group(1))
                break

        return result

    def _extract_company_id(
        self, url: str, ld_json: Dict[str, Any]
    ) -> Optional[str]:
        """
        Derive the company ID from the URL or JSON-LD.
        ZoomInfo URLs often end with a numeric ID.
        """
        if ld_json.get("@id"):
            m = re.search(r"/(\d+)$", str(ld_json["@id"]))
            if m:
                return m.group(1)

        parsed = urlparse(url)
        tail = parsed.path.rstrip("/").split("/")[-1]
        m = re.search(r"(\d+)$", tail)
        if m:
            return m.group(1)
        return None

    def _parse_leadership(self, raw: Any) -> List[LeadershipProfile]:
        profiles: List[LeadershipProfile] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                profiles.append(
                    LeadershipProfile(
                        name=clean_text(item.get("name")),
                        title=clean_text(item.get("title")),
                        url=clean_text(item.get("url")),
                    )
                )
        return profiles

    def _parse_tech_stack(self, raw: Any) -> List[TechStackItem]:
        items: List[TechStackItem] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                items.append(
                    TechStackItem(
                        company_name=clean_text(item.get("company_name")),
                        tech_name=clean_text(item.get("tech_name")),
                    )
                )
        return items

    def _parse_news_items(self, raw: Any) -> List[NewsItem]:
        items: List[NewsItem] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                items.append(
                    NewsItem(
                        title=clean_text(item.get("title")),
                        url=clean_text(item.get("url")),
                    )
                )
        return items

    @staticmethod
    def _parse_float_or_none(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(str(value).strip())
        except (ValueError, TypeError):
            return None