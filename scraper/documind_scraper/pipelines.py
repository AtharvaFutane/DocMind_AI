import re
import json
import psycopg2
from html import unescape
from bs4 import BeautifulSoup
from itemadapter import ItemAdapter


class TextCleanerPipeline:
    """Strips HTML and cleans text from raw_html field."""

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        raw_html = adapter.get("raw_html", "")

        soup = BeautifulSoup(raw_html, "html.parser")

        # Remove navigation, ads, footer elements
        for tag in soup.find_all(["nav", "footer", "header", "script", "style", "aside"]):
            tag.decompose()

        # Get text with spacing
        text = soup.get_text(separator="\n", strip=True)

        # Normalize whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = unescape(text)

        adapter["clean_text"] = text.strip()
        return item


class PostgresPipeline:
    """Saves scraped pages to PostgreSQL."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    @classmethod
    def from_crawler(cls, crawler):
        return cls(db_url=crawler.settings.get("DATABASE_URL"))

    def open_spider(self, spider):
        self.conn = psycopg2.connect(self.db_url)
        self.cursor = self.conn.cursor()

    def close_spider(self, spider):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Skip pages with too little content
        if len(adapter["clean_text"]) < 100:
            return item

        # Convert section_headers list to JSON for JSONB column
        section_headers = adapter.get("section_headers", [])
        section_headers_json = json.dumps(section_headers) if section_headers else "[]"

        self.cursor.execute(
            """
            INSERT INTO pages (url, title, clean_text, section_headers, crawl_job_id, depth, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE
              SET clean_text = EXCLUDED.clean_text,
                  title = EXCLUDED.title,
                  scraped_at = EXCLUDED.scraped_at
            RETURNING id
            """,
            (
                adapter["url"],
                adapter["title"],
                adapter["clean_text"],
                section_headers_json,
                adapter["crawl_job_id"],
                adapter["depth"],
                adapter["scraped_at"],
            ),
        )
        self.conn.commit()
        return item
