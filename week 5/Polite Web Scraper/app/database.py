import sqlite3
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import datetime

class DatabaseManager:
    """
    Handles connection, schema initialization, and transactional queries for
    storing scraped concepts and their detailed sub-sections in SQLite.
    """
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """
        Creates the database tables if they do not already exist.
        """
        # Ensure directories exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            # Table for main concepts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Table for subsections of a concept
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS concept_sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY (concept_id) REFERENCES concepts(id) ON DELETE CASCADE
                );
            """)
            conn.commit()

    def concept_exists(self, name: str) -> bool:
        """
        Checks if a concept by the given name is already saved.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM concepts WHERE name = ? LIMIT 1;", (name,))
            return cursor.fetchone() is not None

    def save_concept(self, name: str, url: str, summary: str, sections: List[Tuple[str, str]]):
        """
        Saves a concept and all of its sections transactionally.
        If the concept already exists, it is overwritten with the fresh scrape.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            # 1. Clean existing record (if any) to prevent orphaned sections
            cursor.execute("DELETE FROM concepts WHERE name = ?;", (name,))
            
            # 2. Insert the parent concept
            cursor.execute(
                "INSERT INTO concepts (name, url, summary) VALUES (?, ?, ?);",
                (name, url, summary)
            )
            concept_id = cursor.lastrowid
            
            # 3. Insert the child sections
            for title, content in sections:
                cursor.execute(
                    "INSERT INTO concept_sections (concept_id, title, content) VALUES (?, ?, ?);",
                    (concept_id, title, content)
                )
            
            conn.commit()

    def get_all_concepts(self) -> List[Dict]:
        """
        Retrieves basic details for all scraped concepts in alphabetical order.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, url, created_at FROM concepts ORDER BY name ASC;")
            return [dict(row) for row in cursor.fetchall()]

    def search_concept(self, query: str) -> List[Dict]:
        """
        Searches concepts by matching the name or summary content.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, url, summary FROM concepts WHERE name LIKE ? OR summary LIKE ? ORDER BY name ASC;",
                (f"%{query}%", f"%{query}%")
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_concept_details(self, concept_id: int) -> Optional[Tuple[Dict, List[Dict]]]:
        """
        Retrieves all details for a concept, including its sub-sections.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get parent concept details
            cursor.execute("SELECT * FROM concepts WHERE id = ?;", (concept_id,))
            concept_row = cursor.fetchone()
            if not concept_row:
                return None
                
            concept_data = dict(concept_row)
            
            # Get child sections details
            cursor.execute("SELECT id, title, content FROM concept_sections WHERE concept_id = ? ORDER BY id ASC;", (concept_id,))
            section_rows = cursor.fetchall()
            sections_data = [dict(row) for row in section_rows]
            
            return concept_data, sections_data

    def get_stats(self) -> Dict[str, int]:
        """
        Gathers general database stats.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM concepts;")
            total_concepts = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM concept_sections;")
            total_sections = cursor.fetchone()[0]
            
            return {
                "total_concepts": total_concepts,
                "total_sections": total_sections
            }
