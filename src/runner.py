import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests

# Ensure local src modules can be imported when running as `python src/runner.py`
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from extractors.data_utils import (  # type: ignore  # noqa: E402
    read_urls_from_file,
)
from extractors.zoominfo_parser import ZoomInfoCompanyParser  # type: ignore  # noqa: E402
from outputs.exporters import DataExporter  # type: ignore  # noqa: E402

def load_settings(settings_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load settings.json if present; otherwise fall back to settings.example.json.
    """
    config_dir = os.path.join(CURRENT_DIR, "config")
    if settings_path:
        candidate_paths = [settings_path]
    else:
        candidate_paths = [
            os.path.join(config_dir, "settings.json"),
            os.path.join(config_dir, "settings.example.json"),
        ]

    for path in candidate_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    raise FileNotFoundError(
        f"No configuration file found. Tried: {', '.join(candidate_paths)}"
    )

def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def fetch_and_parse_company(
    url: str,
    session: requests.Session,
    parser: ZoomInfoCompanyParser,
    timeout: int,
    user_agent: str,
) -> Optional[Dict[str, Any]]:
    logger = logging.getLogger("runner.fetch_and_parse_company")
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        logger.debug(f"Requesting URL: {url}")
        response = session.get(url, timeout=timeout, headers=headers)
        if not response.ok:
            logger.warning(
                "Failed to fetch URL %s: status_code=%s", url, response.status_code
            )
            return None
        html = response.text
        company = parser.parse_company(html, url)
        logger.info("Parsed company '%s' from %s", company.get("name"), url)
        return company
    except requests.RequestException as exc:
        logger.error("Network error while fetching %s: %s", url, exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error while processing %s: %s", url, exc)
    return None

def run(
    input_file: str,
    config_path: Optional[str] = None,
) -> int:
    settings = load_settings(config_path)

    logging_level = settings.get("logging", {}).get("level", "INFO")
    configure_logging(logging_level)
    logger = logging.getLogger("runner")

    request_cfg = settings.get("request", {})
    timeout = int(request_cfg.get("timeout", 15))
    concurrency = int(request_cfg.get("concurrency", 5))
    user_agent = request_cfg.get(
        "user_agent", "ZoomInfoCompaniesScraper/1.0 (+https://bitbash.dev)"
    )

    output_cfg = settings.get("output", {})
    output_dir = os.path.normpath(
        os.path.join(CURRENT_DIR, output_cfg.get("directory", "../data"))
    )
    formats = output_cfg.get("formats", ["json"])
    filename_prefix = output_cfg.get("filename_prefix", "zoominfo_companies")

    logger.info("Loading URLs from %s", input_file)
    urls = read_urls_from_file(input_file)
    if not urls:
        logger.warning("No URLs found in %s. Nothing to do.", input_file)
        return 1

    logger.info("Loaded %d URL(s). Starting scrape.", len(urls))

    parser = ZoomInfoCompanyParser()
    companies: List[Dict[str, Any]] = []

    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_url = {
                executor.submit(
                    fetch_and_parse_company,
                    url,
                    session,
                    parser,
                    timeout,
                    user_agent,
                ): url
                for url in urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        companies.append(result)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Error processing future for %s: %s", url, exc)

    if not companies:
        logger.warning("No companies parsed successfully.")
        return 1

    exporter = DataExporter(output_dir, formats, filename_prefix)
    exporter.export(companies)

    logger.info("Scraping completed. Parsed %d company record(s).", len(companies))
    return 0

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ZoomInfo Companies Scraper runner."
    )
    parser.add_argument(
        "--input",
        "-i",
        default=os.path.normpath(os.path.join(CURRENT_DIR, "../data/input_urls.txt")),
        help="Path to input file containing one ZoomInfo company URL per line.",
    )
    parser.add_argument(
        "--config",
        "-c",
        default=None,
        help="Optional path to configuration JSON file. "
        "If not set, uses src/config/settings.json or settings.example.json.",
    )

    args = parser.parse_args()

    try:
        exit_code = run(args.input, args.config)
    except FileNotFoundError as exc:
        # Config-related issues
        print(f"Configuration error: {exc}", file=sys.stderr)
        exit_code = 1
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("runner").exception("Fatal error: %s", exc)
        exit_code = 1

    sys.exit(exit_code)

if __name__ == "__main__":
    main()