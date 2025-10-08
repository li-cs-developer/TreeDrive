CC = clang
all: screen_scraper
screen_scraper: screen_scraper.c
	$(CC) -o screen_scraper screen_scraper.c
clean:
	rm -f screen_scraper