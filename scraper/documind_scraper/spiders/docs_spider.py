import scrapy
from urllib.parse import urlparse
from datetime import datetime, timezone
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from ..items import DocPageItem


class DocsSpider(CrawlSpider):
    """
    Recursively crawls any documentation website.
    Stays within the same domain and path prefix as the start URL.

    Usage:
        scrapy crawl docs_spider \
            -a start_url=https://fastapi.tiangolo.com \
            -a crawl_job_id=123 \
            -s DEPTH_LIMIT=10
    """
    name = "docs_spider"

    def __init__(self, start_url: str, crawl_job_id: str, *args, **kwargs):
        self.start_url = start_url.rstrip("/")
        self.crawl_job_id = int(crawl_job_id)

        parsed = urlparse(self.start_url)
        self.allowed_domain = parsed.netloc
        self.path_prefix = parsed.path or "/"

        self.allowed_domains = [self.allowed_domain]
        self.start_urls = [self.start_url]

        # Only follow links that stay within the same path prefix
        self.rules = (
            Rule(
                LinkExtractor(
                    allow_domains=[self.allowed_domain],
                    allow=[rf"{self.path_prefix}.*"],
                    deny=[
                        r"\.(pdf|zip|tar|gz|jpg|jpeg|png|gif|svg|ico|css|js)$",
                        r"#.*",             # anchor links
                        r"/api/",           # API reference JSON (usually too noisy)
                        r"changelog",
                        r"release-notes",
                    ],
                    unique=True,
                ),
                callback="parse_doc_page",
                follow=True,
            ),
        )

        super().__init__(*args, **kwargs)

    def parse_doc_page(self, response):
        # Skip non-HTML responses
        content_type = response.headers.get("Content-Type", b"").decode()
        if "text/html" not in content_type:
            return

        # Extract title
        title = (
            response.css("title::text").get()
            or response.css("h1::text").get()
            or response.url
        ).strip()

        # Extract main content — try common doc selectors
        content_selectors = [
            "article",
            "main",
            ".content",
            ".documentation",
            ".docs-content",
            "#content",
            ".md-content",      # MkDocs
            ".rst-content",     # Sphinx
            "body",             # fallback
        ]
        raw_html = ""
        for selector in content_selectors:
            raw_html = response.css(selector).get(default="")
            if raw_html:
                break

        # Extract section headers for metadata
        section_headers = response.css("h2::text, h3::text").getall()

        yield DocPageItem(
            url=response.url,
            title=title,
            raw_html=raw_html,
            clean_text="",          # filled by TextCleanerPipeline
            section_headers=section_headers,
            crawl_job_id=self.crawl_job_id,
            depth=response.meta.get("depth", 0),
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )
