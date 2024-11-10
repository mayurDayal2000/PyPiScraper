# PyPiScraper

PyPiScraper is a Python-based web scraper designed to extract project information
from [PyPI (Python Package Index)](https://pypi.org/). The scraper navigates through search results, collects data on
individual projects, and stores the information in a Supabase database for persistent storage and easy retrieval.

## Features

- **Web Scraping**: Scrapes project titles, descriptions, maintainers, emails, and GitHub repositories from PyPI.
- **Rate Limiting**: Implements rate limiting to prevent overloading PyPI servers.
- **Caching**: Utilizes request caching to minimize redundant network calls.
- **Error Handling**: Robust error handling with retries and exponential backoff.
- **Progress Saving**: Saves scraping progress to resume from the last state.
- **Database Integration**: Stores scraped data in a Supabase PostgreSQL database.
- **Data Modeling**: Uses data classes (dataclasses) for structured data representation.

## Prerequisites

- Python 3.9 or higher
- Supabase account and project


