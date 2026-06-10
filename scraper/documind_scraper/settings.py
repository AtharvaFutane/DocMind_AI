BOT_NAME = "documind_scraper"
SPIDER_MODULES = ["documind_scraper.spiders"]
NEWSPIDER_MODULE = "documind_scraper.spiders"

# Respectful crawling
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 0.5
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 3.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# Don't re-visit the same URL
DUPEFILTER_CLASS = "scrapy.dupefilters.RFPDupeFilter"

# Enable caching for dev (disable in production re-crawls)
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400
HTTPCACHE_DIR = "data/.scrapy_cache"

# Pipelines
ITEM_PIPELINES = {
    "documind_scraper.pipelines.TextCleanerPipeline": 100,
    "documind_scraper.pipelines.PostgresPipeline": 200,
}

# Feed exports
FEEDS = {}

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "data/logs/scrapy.log"

# User agent — be transparent
USER_AGENT = "DocuMind-Bot/1.0 (educational project)"

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"
