import sys
from pathlib import Path
from app.config import SEED_CONCEPTS, DATABASE_PATH, USER_AGENT
from app.robots import RobotsManager
from app.database import DatabaseManager
from app.scraper import WikipediaScraper

def print_separator(char="=", length=65):
    print(char * length)

def print_header(title):
    print_separator("#")
    print(f" {title.upper()} ".center(65, " "))
    print_separator("#")

def display_menu():
    print("\n")
    print_header("Polite Web Scraper Dashboard")
    print(" 1. Run Scraper (Crawl Wikipedia Backend Concepts)")
    print(" 2. Search & Browse Scraped Glossary")
    print(" 3. View Database Statistics")
    print(" 4. Test URL robots.txt Compliance")
    print(" 5. Exit")
    print_separator("-")

def run_scraper_flow(scraper: WikipediaScraper):
    print("\n")
    print_header("Run Scraper Flow")
    print("Select target concepts:")
    print(" A. Scrape default seed list (11 concepts: Redis, Docker, FastAPI, REST, etc.)")
    print(" B. Scrape a custom concept")
    choice = input("Choose option (A/B) [Default: A]: ").strip().upper() or "A"
    
    force_input = input("Force re-scrape existing concepts? (y/n) [Default: n]: ").strip().lower()
    force = force_input == "y"
    
    concepts_to_scrape = []
    if choice == "B":
        custom_concept = input("Enter a single Wikipedia article slug to scrape (e.g. 'Kubernetes'): ").strip()
        if custom_concept:
            concepts_to_scrape.append(custom_concept)
        else:
            print("[Error] No concept entered. Aborting.")
            return
    else:
        concepts_to_scrape = SEED_CONCEPTS
        
    print_separator("-")
    print(f"Starting crawl of {len(concepts_to_scrape)} concept(s)...")
    print(f"Configured User-Agent: {USER_AGENT}")
    print_separator("-")
    
    start_time = sys.float_info.max # Or python time
    import time
    start_t = time.time()
    
    scraper.crawl_list(concepts_to_scrape, force=force)
    
    duration = time.time() - start_t
    print_separator("-")
    print(f"Crawl finished in {duration:.2f} seconds.")
    print_separator("-")

def search_glossary_flow(db_mgr: DatabaseManager):
    print("\n")
    print_header("Search Glossary")
    query = input("Enter search query (or leave blank to list all): ").strip()
    
    if query:
        results = db_mgr.search_concept(query)
        print(f"\nFound {len(results)} matching concepts:")
    else:
        results = db_mgr.get_all_concepts()
        print(f"\nAll concepts currently in database ({len(results)} total):")
        
    if not results:
        print("No concepts found in database. Run the scraper first.")
        return
        
    print_separator("-")
    for i, row in enumerate(results, 1):
        print(f" {i:2d}. {row['name']}")
    print_separator("-")
    
    select_choice = input("Enter number to view details (or press Enter to return): ").strip()
    if not select_choice.isdigit():
        return
        
    idx = int(select_choice) - 1
    if 0 <= idx < len(results):
        concept_id = results[idx]["id"]
        details = db_mgr.get_concept_details(concept_id)
        if not details:
            print("[Error] Details not found.")
            return
            
        concept, sections = details
        print("\n" + "=" * 65)
        print(f" CONCEPT: {concept['name']}".upper())
        print(f" Source URL: {concept['url']}")
        print(f" Scraped at: {concept['created_at']}")
        print("=" * 65)
        print("\n--- INTRODUCTION SUMMARY ---")
        print(concept["summary"])
        print("\n--- SECTIONS ---")
        
        if not sections:
            print("No subsections parsed.")
        else:
            for sec in sections:
                print(f"\n>> {sec['title']}")
                print(sec["content"])
        print("=" * 65)
        input("\nPress Enter to return to menu...")

def show_stats_flow(db_mgr: DatabaseManager):
    print("\n")
    print_header("Database Statistics")
    stats = db_mgr.get_stats()
    print(f" Total Concepts Scraped : {stats['total_concepts']}")
    print(f" Total Concept Sections : {stats['total_sections']}")
    print_separator("-")
    
    concepts = db_mgr.get_all_concepts()
    if concepts:
        print("Scraped Concept Names:")
        for c in concepts:
            print(f" - {c['name']} (Scraped on: {c['created_at']})")
    else:
        print("No concepts cached in the database yet.")
    print_separator("-")
    input("Press Enter to return to menu...")

def test_url_flow(robots_mgr: RobotsManager):
    print("\n")
    print_header("Test URL Robots.txt Compliance")
    url = input("Enter full URL to test: ").strip()
    if not url:
        print("[Error] Empty URL entered.")
        return
        
    print_separator("-")
    print(f"Checking with User-Agent: {robots_mgr.user_agent}")
    is_ok = robots_mgr.is_allowed(url)
    delay = robots_mgr.get_crawl_delay(url)
    
    status = "ALLOWED ✅" if is_ok else "DISALLOWED ❌"
    print(f" Crawl Status  : {status}")
    print(f" Crawl Delay   : {delay if delay else 'None specified (defaults to application default)'}")
    print_separator("-")
    input("Press Enter to return to menu...")

def main():
    # Load settings and managers
    db_mgr = DatabaseManager(DATABASE_PATH)
    robots_mgr = RobotsManager(USER_AGENT)
    scraper = WikipediaScraper(robots_mgr, db_mgr)
    
    while True:
        try:
            display_menu()
            choice = input("Enter your choice (1-5): ").strip()
            
            if choice == "1":
                run_scraper_flow(scraper)
            elif choice == "2":
                search_glossary_flow(db_mgr)
            elif choice == "3":
                show_stats_flow(db_mgr)
            elif choice == "4":
                test_url_flow(robots_mgr)
            elif choice == "5":
                print("\nExiting. Thank you for using the Polite Scraper!")
                break
            else:
                print("\n[Error] Invalid option. Please enter 1-5.")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled. Exiting...")
            break

if __name__ == "__main__":
    main()
