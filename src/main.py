import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Ensure local src modules can be imported when running "python src/main.py"
CURRENT_FILE = Path(__file__).resolve()
SRC_DIR = CURRENT_FILE.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extractors.zoominfo_parser import ZoomInfoCompanyScraper  # type: ignore  # noqa: E402
from extractors.utils_data import load_settings, get_logger  # type: ignore  # noqa: E402
from outputs.json_exporter import JSONExporter  # type: ignore  # noqa: E402

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ZoomInfo Companies Scraper - scrape ZoomInfo company profiles into JSON."
    )
    parser.add_argument(
        "--input",
        "-i",
        default=str(SRC_DIR.parent / "data" / "input_profiles.txt"),
        help="Path to input text file containing ZoomInfo company profile URLs (one per line).",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(SRC_DIR.parent / "data" / "sample_output.json"),
        help="Path to output JSON file where scraped data will be stored.",
    )
    parser.add_argument(
        "--settings",
        "-s",
        default=None,
        help="Optional path to settings JSON file. "
             "If not provided, settings.json or settings.example.json in src/config/ will be used.",
    )
    return parser.parse_args()

def read_urls(input_path: Path, logger: logging.Logger) -> List[str]:
    if not input_path.exists():
        logger.error("Input profiles file not found at %s", input_path)
        raise FileNotFoundError(f"Input profiles file not found at {input_path}")

    urls: List[str] = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            urls.append(stripped)

    if not urls:
        logger.warning("No URLs found in input file: %s", input_path)
    else:
        logger.info("Loaded %d URLs from %s", len(urls), input_path)

    return urls

def run() -> None:
    args = parse_args()

    # Load settings
    settings = load_settings(args.settings)
    log_level = settings.get("log_level", "INFO")
    root_logger = get_logger("zoominfo_main", log_level)

    root_logger.debug("Settings loaded: %s", json.dumps(settings, indent=2))

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    root_logger.info("Using input file: %s", input_path)
    root_logger.info("Using output file: %s", output_path)

    urls = read_urls(input_path, root_logger)
    if not urls:
        root_logger.error("No URLs to process. Exiting.")
        return

    scraper = ZoomInfoCompanyScraper(settings=settings, logger=get_logger("zoominfo_scraper", log_level))
    exporter = JSONExporter(output_path)

    all_results: List[Dict[str, Any]] = []

    for idx, url in enumerate(urls, start=1):
        root_logger.info("Processing %d/%d: %s", idx, len(urls), url)
        try:
            result = scraper.scrape_company(url)
            all_results.append(result)
        except Exception as exc:  # noqa: BLE001
            root_logger.exception("Failed to scrape URL %s: %s", url, exc)
            all_results.append(
                {
                    "url": url,
                    "id": None,
                    "name": None,
                    "description": None,
                    "revenue": None,
                    "revenue_currency": None,
                    "stock_symbol": None,
                    "website": None,
                    "employees": None,
                    "industry": [],
                    "headquarters": None,
                    "phone_number": None,
                    "total_funding_amount": None,
                    "most_recent_funding_amount": None,
                    "funding_currency": None,
                    "funding_rounds": None,
                    "leadership": [],
                    "business_classification_codes": [],
                    "ceo_rating": None,
                    "enps_score": None,
                    "tech_stack": [],
                    "social_media": [],
                    "news_and_media": [],
                    "error": str(exc),
                }
            )

    exporter.export(all_results)
    root_logger.info("Scraping finished. %d records written to %s", len(all_results), output_path)

if __name__ == "__main__":
    run()