import urllib.parse
from urllib.robotparser import RobotFileParser

class RobotsManager:
    """
    Manages robots.txt rules for different domains, caching parsers
    to avoid redundant network requests.
    """
    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self._parsers = {}

    def _get_robots_url(self, url: str) -> str:
        parsed_url = urllib.parse.urlparse(url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

    def get_parser(self, url: str) -> RobotFileParser:
        robots_url = self._get_robots_url(url)
        
        if robots_url not in self._parsers:
            parser = RobotFileParser()
            try:
                # Fetch robots.txt using requests with custom User-Agent to avoid HTTP 403 Forbidden blocks
                import requests
                headers = {"User-Agent": self.user_agent}
                response = requests.get(robots_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                elif response.status_code == 404:
                    # If robots.txt does not exist, everything is allowed by default
                    parser.parse([])
                else:
                    print(f"[Warning] Failed to fetch robots.txt at {robots_url} (HTTP {response.status_code}). Defaulting to allow.")
                    parser.parse([])
                    
                self._parsers[robots_url] = parser
            except Exception as e:
                print(f"[Warning] Error reading robots.txt from {robots_url}: {e}. Defaulting to allow.")
                parser.parse([])
                self._parsers[robots_url] = parser
                
        return self._parsers[robots_url]

    def is_allowed(self, url: str) -> bool:
        """
        Check if the configured User-Agent is permitted to crawl the specified URL.
        """
        parser = self.get_parser(url)
        if parser is None:
            return True
        return parser.can_fetch(self.user_agent, url)

    def get_crawl_delay(self, url: str) -> float:
        """
        Extract the Crawl-delay directive for our User-Agent if specified.
        Returns None if not defined.
        """
        parser = self.get_parser(url)
        if parser is None:
            return None
        try:
            delay = parser.crawl_delay(self.user_agent)
            return float(delay) if delay else None
        except Exception:
            return None
