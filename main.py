from app.scrapper import PyPiScrapper


def main():
    url = "https://pypi.org/search/?&o=-created&c=Programming+Language+%3A%3A+Python"

    scrapper = PyPiScrapper(url)
    scrapper.scrape_all_projects()


if __name__ == '__main__':
    main()
