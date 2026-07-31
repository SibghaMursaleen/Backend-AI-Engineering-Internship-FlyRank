import re
import time
import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
from typing import Tuple, List, Optional
from app.config import USER_AGENT, DEFAULT_DELAY, WIKIPEDIA_BASE_URL
from app.robots import RobotsManager
from app.database import DatabaseManager

def clean_text(text: str) -> str:
    """
    Cleans Wikipedia markup leftover footprints:
    - Removes citations like [1], [citation needed], [a], etc.
    - Collapses multiple spaces and tabs to a single space.
    - Replaces non-breaking space characters with normal spaces.
    """
    # Remove citations like [1], [12], [citation needed], [a], etc.
    text = re.sub(r'\[[a-zA-Z0-9\s,\-]*\]', '', text)
    # Collapse horizontal spaces/tabs
    text = re.sub(r'[ \t]+', ' ', text)
    # Remove non-breaking spaces
    text = text.replace('\xa0', ' ')
    return text.strip()

class WikipediaScraper:
    """
    Orchestrates the fetch -> parse -> extract -> clean -> structure pipeline
    for scraping Wikipedia pages politely.
    """
    def __init__(self, robots_mgr: RobotsManager, db_mgr: DatabaseManager):
        self.robots_mgr = robots_mgr
        self.db_mgr = db_mgr
        self.headers = {"User-Agent": USER_AGENT}

    def scrape_concept(self, concept_name: str, force: bool = False) -> str:
        """
        Scrapes a concept page from Wikipedia, processes its contents,
        and saves it to the database.
        
        Returns:
            "Success" if successfully scraped and stored.
            "Skipped" if skipped due to robots.txt or because it was already scraped.
            "Not Found" if the page does not exist.
            "Error" if an unrecoverable request or processing error occurs.
        """
        concept_url = f"{WIKIPEDIA_BASE_URL}{concept_name}"
        
        # 1. Skip if already scraped (unless forced refresh)
        if not force and self.db_mgr.concept_exists(concept_name):
            print(f"[Info] Skipped '{concept_name}': Already exists in database.")
            return "Skipped"

        # 2. Check robots.txt compliance
        if not self.robots_mgr.is_allowed(concept_url):
            print(f"[Warning] Skipped '{concept_name}': Disallowed by robots.txt rule.")
            return "Skipped"

        print(f"[Fetch] Scraping '{concept_name}' from {concept_url}...")
        
        # 3. Fetch with Retry Logic and Timeout
        response = None
        max_retries = 3
        retry_delay = 3.0
        
        for attempt in range(max_retries):
            try:
                response = requests.get(concept_url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    break
                elif response.status_code == 404:
                    print(f"[Error] Concept page '{concept_name}' does not exist (404).")
                    return "Not Found"
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    sleep_time = int(retry_after) if retry_after and retry_after.isdigit() else int(retry_delay * 2)
                    print(f"[Warning] Rate limited (429). Backing off for {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    print(f"[Warning] Fetch got code {response.status_code}. Retrying ({attempt+1}/{max_retries})...")
                    time.sleep(retry_delay)
            except RequestException as e:
                print(f"[Warning] Connection error: {e}. Retrying ({attempt+1}/{max_retries})...")
                time.sleep(retry_delay)
        
        if not response or response.status_code != 200:
            print(f"[Error] Failed to fetch '{concept_name}' after {max_retries} attempts.")
            return "Error"

        # 4. Parse HTML & Decompose unwanted items
        try:
            title, summary, sections = self._parse_html(response.text)
            
            if not summary and not sections:
                print(f"[Warning] Page parsed but no body content extracted for '{concept_name}'.")
                return "Error"

            # 5. Structure & Save in DB
            self.db_mgr.save_concept(concept_name, concept_url, summary, sections)
            print(f"[Structure] Saved '{concept_name}' with {len(sections)} sections in SQLite.")
            return "Success"
            
        except Exception as e:
            print(f"[Error] Parsing error on '{concept_name}': {e}")
            return "Error"

    def _parse_html(self, html: str) -> Tuple[str, str, List[Tuple[str, str]]]:
        """
        Parses Wikipedia body HTML using BeautifulSoup.
        Supports both Vector 2022 `<section>` grouping and older flat-tag layouts.
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # Get page title
        title_el = soup.find(id="firstHeading")
        title = title_el.get_text().strip() if title_el else "Unknown Title"
        
        # Target main content container
        content_div = soup.find(class_="mw-parser-output")
        if not content_div:
            return title, "", []
            
        # Clean the DOM: remove sidebars, maps, metadata tables, reference popups, edit tags
        unwanted_selectors = [
            "table.infobox", "div.toc", "table.ambox", "div.navbox", 
            ".mw-editsection", "sup.reference", ".hatnote", ".navigation-not-search",
            "style", "script", ".gallery", "table.sidebar", ".sidebar", 
            ".vertical-navbox", ".metadata"
        ]
        for selector in unwanted_selectors:
            for element in content_div.select(selector):
                element.decompose()
                
        # Wikipedia Vector 2022 layout uses <section> tags to group main contents
        sections_elements = content_div.find_all("section", recursive=False)
        
        intro_paragraphs = []
        sections = []
        
        if sections_elements:
            # Modern <section>-grouped layout
            for sec in sections_elements:
                h2_el = sec.find("h2")
                
                # Gather content inside this section
                sec_paragraphs = []
                for child in sec.find_all(["p", "ul", "ol", "h3", "h4"]):
                    if child.name in ["h3", "h4"]:
                        h_text = child.get_text().strip()
                        sec_paragraphs.append(f"### {h_text}")
                    elif child.name in ["ul", "ol"]:
                        list_items = []
                        for li in child.find_all("li", recursive=False):
                            li_text = clean_text(li.get_text())
                            if li_text:
                                list_items.append(f"- {li_text}")
                        text = "\n".join(list_items)
                        if text:
                            sec_paragraphs.append(text)
                    else:  # p
                        text = clean_text(child.get_text())
                        if text:
                            sec_paragraphs.append(text)
                            
                body_content = "\n\n".join(sec_paragraphs).strip()
                if not body_content:
                    continue
                    
                if h2_el:
                    current_section_title = h2_el.get_text().strip()
                    
                    # Check for utility section names to exclude (e.g. references, external links)
                    excluded_headers = [
                        "see also", "references", "further reading", "external links",
                        "notes", "notes and references", "bibliography", "sources", "gallery"
                    ]
                    if any(ex in current_section_title.lower() for ex in excluded_headers):
                        continue  # Skip this entire section
                        
                    sections.append((current_section_title, body_content))
                else:
                    # No h2 means this is the introduction summary!
                    intro_paragraphs.append(body_content)
        else:
            # Fallback for flat layout (old MediaWiki skins or mirrors)
            current_section_title = None
            current_section_paragraphs = []
            
            for child in content_div.find_all(recursive=False):
                if child.name == "h2":
                    # Save previous section
                    if current_section_title:
                        section_body = "\n\n".join(current_section_paragraphs).strip()
                        if section_body:
                            sections.append((current_section_title, section_body))
                        current_section_paragraphs = []
                    
                    # Identify new section
                    headline = child.find(class_="mw-headline")
                    current_section_title = headline.get_text().strip() if headline else child.get_text().strip()
                    
                    excluded_headers = [
                        "see also", "references", "further reading", "external links",
                        "notes", "notes and references", "bibliography", "sources", "gallery"
                    ]
                    if any(ex in current_section_title.lower() for ex in excluded_headers):
                        current_section_title = None
                        
                elif child.name in ["h3", "h4"]:
                    if current_section_title:
                        h_text = child.get_text().strip()
                        current_section_paragraphs.append(f"### {h_text}")
                        
                elif child.name in ["p", "ul", "ol"]:
                    if child.name in ["ul", "ol"]:
                        list_items = []
                        for li in child.find_all("li", recursive=False):
                            li_text = clean_text(li.get_text())
                            if li_text:
                                list_items.append(f"- {li_text}")
                        text = "\n".join(list_items)
                    else:
                        text = clean_text(child.get_text())
                        
                    if not text:
                        continue
                        
                    if current_section_title is None:
                        if not sections:
                            intro_paragraphs.append(text)
                    else:
                        current_section_paragraphs.append(text)
                        
            # Add final section
            if current_section_title:
                section_body = "\n\n".join(current_section_paragraphs).strip()
                if section_body:
                    sections.append((current_section_title, section_body))
                    
        intro_summary = "\n\n".join(intro_paragraphs).strip()
        return title, intro_summary, sections

    def crawl_list(self, concepts: List[str], force: bool = False):
        """
        Crawls a list of concepts politely, incorporating crawl delay spacing.
        """
        for i, concept in enumerate(concepts):
            # Check delay for this endpoint
            concept_url = f"{WIKIPEDIA_BASE_URL}{concept}"
            delay = self.robots_mgr.get_crawl_delay(concept_url)
            
            if delay is None:
                delay = DEFAULT_DELAY
                
            status = self.scrape_concept(concept, force=force)
            
            # Apply polite rate-limit delay if this isn't the last concept and we actually fetched it
            if i < len(concepts) - 1 and status in ["Success", "Error"]:
                print(f"[Pace] Waiting {delay}s crawl delay before next fetch...")
                time.sleep(delay)
