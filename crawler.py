import asyncio
import re
import logging
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup
import time
import json
import os
from collections import defaultdict
import argparse
from aiohttp import ClientSession, TCPConnector
from aiohttp.client_exceptions import ClientError, ClientConnectorError, ServerDisconnectedError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ecommerce_crawler")

class EcommerceCrawler:
    def __init__(self, domains, max_concurrent_requests=5, max_retries=3, delay=1):
        """
        Initialize the crawler with configuration parameters
        
        Args:
            domains (list): List of e-commerce domains to crawl
            max_concurrent_requests (int): Maximum number of concurrent requests
            max_retries (int): Maximum number of retry attempts for failed requests
            delay (float): Delay between requests to the same domain in seconds
        """
        self.domains = domains
        self.max_concurrent_requests = max_concurrent_requests
        self.max_retries = max_retries
        self.delay = delay
        
        # Stores discovered URLs
        self.visited_urls = set()
        self.product_urls = defaultdict(set)
        self.queue = []
        
        # Common product URL patterns across e-commerce sites
        self.product_url_patterns = [
            r'/product/', r'/item/', r'/p/', r'/pd/', r'/dp/', 
            r'/products/', r'/-pr-', r'/buy/', r'/shop/',
            # Site specific patterns 
            r'virgio\.com.*/shop/',
            r'tatacliq\.com.*/p-',
            r'nykaafashion\.com.*/buy/',
            r'westside\.com.*/product/'
        ]

    async def is_product_url(self, url):
        """
        Check if a URL is likely to be a product page
        
        Args:
            url (str): URL to check
            
        Returns:
            bool: True if the URL is likely a product page, False otherwise
        """
        # Check against common product URL patterns
        for pattern in self.product_url_patterns:
            if re.search(pattern, url):
                return True
                
        # Additional heuristics can be added here
        return False

    async def fetch_url(self, url, session):
        """
        Fetch a URL and return the HTML content
        
        Args:
            url (str): URL to fetch
            session (ClientSession): aiohttp client session
            
        Returns:
            str: HTML content or None if request failed
        """
        for attempt in range(self.max_retries):
            try:
                async with session.get(url, timeout=30, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:  # Too many requests
                        wait_time = 5 * (attempt + 1)
                        logger.warning(f"Rate limited on {url}. Waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                        return None
            except (ClientError, asyncio.TimeoutError, ServerDisconnectedError) as e:
                logger.warning(f"Error fetching {url} (attempt {attempt+1}/{self.max_retries}): {e}")
                await asyncio.sleep(2 * (attempt + 1))
        
        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None

    async def extract_links(self, html, base_url):
        """
        Extract all links from HTML content
        
        Args:
            html (str): HTML content
            base_url (str): Base URL for resolving relative links
            
        Returns:
            list: List of absolute URLs found in the HTML
        """
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        # Extract all href attributes from anchor tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                absolute_url = urljoin(base_url, href)
                # Only keep URLs from the same domain
                if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                    links.append(absolute_url)
        
        return links

    async def process_url(self, url, domain, session, semaphore):
        """
        Process a URL: fetch it, check if it's a product page, and extract new links
        
        Args:
            url (str): URL to process
            domain (str): Domain being crawled
            session (ClientSession): aiohttp client session
            semaphore (Semaphore): Semaphore for limiting concurrent requests
        """
        if url in self.visited_urls:
            return
        
        # Add to visited set immediately to prevent re-queuing
        self.visited_urls.add(url)
        
        # Check if it's already a product URL before fetching
        if await self.is_product_url(url):
            logger.info(f"Found product URL: {url}")
            self.product_urls[domain].add(url)
        
        async with semaphore:
            html = await self.fetch_url(url, session)
            await asyncio.sleep(self.delay)  # Respect robots.txt implicitly
        
        if not html:
            return
        
        # Extract all links from the page
        links = await self.extract_links(html, url)
        
        # Add new unvisited links to the queue
        for link in links:
            if link not in self.visited_urls:
                self.queue.append((link, domain))

    async def crawl_domain(self, domain):
        """
        Crawl a specific domain to find product URLs
        
        Args:
            domain (str): Domain to crawl
        """
        logger.info(f"Starting crawl for domain: {domain}")
        
        start_time = time.time()
        self.queue = [(domain, domain)]
        
        # Create a semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        # Create a ClientSession with a connection limit
        connector = TCPConnector(limit=self.max_concurrent_requests)
        async with ClientSession(connector=connector) as session:
            # Process URLs until queue is empty or max limit is reached
            tasks = []
            processed_count = 0
            max_process_limit = 1000  # Adjust as needed for depth vs. time tradeoff
            
            while self.queue and processed_count < max_process_limit:
                # Process up to N URLs concurrently
                batch_size = min(50, len(self.queue))
                batch = [self.queue.pop(0) for _ in range(batch_size)]
                
                for url, domain_name in batch:
                    task = asyncio.create_task(self.process_url(url, domain_name, session, semaphore))
                    tasks.append(task)
                    processed_count += 1
                
                if processed_count % 100 == 0:
                    logger.info(f"Processed {processed_count} URLs for {domain}, found {len(self.product_urls[domain])} product URLs")
                
                # Wait for the current batch to complete
                await asyncio.gather(*tasks)
                tasks = []
        
        # Log a summary of the results
        elapsed_time = time.time() - start_time
        logger.info(f"Completed crawl for {domain} in {elapsed_time:.2f} seconds")
        logger.info(f"Visited {len(self.visited_urls)} URLs, found {len(self.product_urls[domain])} product URLs")

    async def crawl_all_domains(self):
        """
        Crawl all domains sequentially
        """
        for domain in self.domains:
            # Reset visited URLs between domains
            self.visited_urls.clear()
            await self.crawl_domain(domain)

    def save_results(self, output_file="product_urls.json"):
        """
        Save the discovered product URLs to a JSON file
        
        Args:
            output_file (str): Path to the output file
        """
        # Convert sets to lists for JSON serialization
        results = {domain: list(urls) for domain, urls in self.product_urls.items()}
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {output_file}")
        
        # Also save individual files per domain
        os.makedirs("results", exist_ok=True)
        for domain, urls in self.product_urls.items():
            domain_name = urlparse(domain).netloc.replace(".", "_")
            filename = f"results/{domain_name}_products.json"
            with open(filename, 'w') as f:
                json.dump(list(urls), f, indent=2)
            logger.info(f"Domain results saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description="E-commerce Product URL Crawler")
    parser.add_argument("--domains", nargs="+", help="List of domains to crawl", 
                        default=[
                            "https://www.virgio.com/",
                            "https://www.tatacliq.com/",
                            "https://nykaafashion.com/",
                            "https://www.westside.com/"
                        ])
    parser.add_argument("--concurrent", type=int, default=5, help="Maximum concurrent requests per domain")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds")
    parser.add_argument("--output", default="product_urls.json", help="Output file name")
    
    args = parser.parse_args()
    
    crawler = EcommerceCrawler(
        domains=args.domains,
        max_concurrent_requests=args.concurrent,
        delay=args.delay
    )
    
    # Run the crawler
    asyncio.run(crawler.crawl_all_domains())
    
    # Save the results
    crawler.save_results(args.output)

if __name__ == "__main__":
    main()