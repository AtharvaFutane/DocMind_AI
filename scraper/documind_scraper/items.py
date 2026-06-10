import scrapy


class DocPageItem(scrapy.Item):
    """Represents a single scraped documentation page."""
    url = scrapy.Field()
    title = scrapy.Field()
    raw_html = scrapy.Field()
    clean_text = scrapy.Field()
    section_headers = scrapy.Field()   # list of h2/h3 headings on page
    crawl_job_id = scrapy.Field()
    depth = scrapy.Field()
    scraped_at = scrapy.Field()
