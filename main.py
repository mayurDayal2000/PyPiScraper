import logging

from app.scrapper import PyPiScrapper


def main():
    # initialize logging
    logger = logging.getLogger(__name__)
    logger.info("Starting PyPi Scrapper")

    url = "https://pypi.org/search/?&o=-created&c=Programming+Language+%3A%3A+Python"

    scrapper = PyPiScrapper(url)

    try:
        scrapper.scrape_all_projects()
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
    finally:
        logger.info("PyPi Scrapper has completed execution.")


if __name__ == "__main__":
    main()
