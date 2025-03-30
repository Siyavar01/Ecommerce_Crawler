# E-commerce Product URL Crawler

This project implements a scalable, asynchronous web crawler designed to discover product URLs across multiple e-commerce websites. The crawler can efficiently handle multiple domains and is capable of identifying product pages based on URL patterns and site structure analysis.

## Features

- Asynchronous crawling for high performance
- Intelligent product URL detection using pattern matching
- Rate limiting and polite crawling behavior
- Robust error handling with retries
- Scalable architecture that can handle hundreds of domains
- Detailed logging for monitoring and debugging
- Configurable concurrency and delay settings

## Project Structure

```
ecommerce-crawler/
├── crawler.py                # Main crawler implementation
├── requirements.txt          # Project dependencies
├── README.md                 # Project documentation
└── results/                  # Output directory for crawler results
```

## Approach for Identifying Product URLs

The crawler identifies product URLs using several strategies:

1. **Pattern Matching**: Uses common URL patterns found in e-commerce sites:
   - General patterns like `/product/`, `/item/`, `/p/`
   - Website-specific patterns for the required domains

2. **URL Structure Analysis**: Examines URL structure to identify product pages
   - Looks for product IDs, SKUs, and other identifiers in URL paths

3. **Content-Based Detection**: Analyzes page content to confirm product pages
   - Although not fully implemented in the current version, the architecture supports extending to include HTML analysis for product indications like price elements, "Add to Cart" buttons, etc.

## Requirements

- Python 3.7+
- BeautifulSoup4
- aiohttp
- Other dependencies listed in requirements.txt

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/ecommerce-crawler.git
   cd ecommerce-crawler
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

Run the crawler with default settings:

```bash
python crawler.py
```

This will crawl the 4 required domains with default settings and output results to `product_urls.json`.

### Advanced Usage

Customize the crawler behavior with command-line arguments:

```bash
python crawler.py --domains https://www.example.com/ https://www.anothersite.com/ --concurrent 10 --delay 0.5 --output custom_output.json
```

Arguments:
- `--domains`: List of domains to crawl (space-separated)
- `--concurrent`: Maximum number of concurrent requests per domain
- `--delay`: Delay between requests in seconds
- `--output`: Output file name

## Output Format

The crawler produces a JSON file mapping each domain to its list of product URLs:

```json
{
  "https://www.virgio.com/": [
    "https://www.virgio.com/shop/product1",
    "https://www.virgio.com/shop/product2",
    ...
  ],
  "https://www.tatacliq.com/": [
    "https://www.tatacliq.com/p-product1",
    "https://www.tatacliq.com/p-product2",
    ...
  ],
  ...
}
```

Individual results for each domain are also saved in the `results/` directory.

## Limitations and Future Improvements

1. **JavaScript Rendering**: The current implementation doesn't support JavaScript rendering, which may limit discovery on highly dynamic sites that load content via JS. A future improvement could integrate with a headless browser like Playwright or Puppeteer.

2. **Advanced Content Analysis**: Currently relies primarily on URL patterns. Could be enhanced with machine learning to identify product pages based on page content.

3. **Respect for robots.txt**: A more robust implementation would parse each site's robots.txt file.

4. **Distributed Crawling**: For extremely large sites, a distributed architecture using message queues could be implemented.

## Performance Considerations

- The crawler uses asynchronous I/O to maximize throughput while minimizing resource usage
- Rate limiting is implemented to be respectful to server resources
- Exponential backoff is used for retries to handle temporary failures

## Error Handling

The crawler implements robust error handling:
- Connection timeouts and errors
- Rate limiting detection and backoff
- Malformed HTML handling
- Domain-specific edge cases