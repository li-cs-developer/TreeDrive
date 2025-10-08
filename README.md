File Sharing Server
===
The file share server file is called `server.py`

To run `server.py`, type the following in the terminal then hit enter: 

```bash
python3 server.py 
```
An example the terminal would print: `
TreeDrive server listening on host - localhost port 8125
`. where `localhost` is the hostname. This is needed to run webserver.py

Web Server
===
The web server file is called `webserver.py`

`SERVER_HOST` in `webserver.py` needs to be changed before running. 

To change the `SERVER_HOST`, type the following in the terminal then hit enter: 

```bash
vi webserver.py  
```
Then press `i` to enter insert mode, on line 12, change `SERVER_HOST = ''` to the hostname. For example `HOST = 'localhost'` if `server.py` is listening on `localhost`. Then save the change and exit by pressing `esc` and `:wq` then hit enter to go back to the terminal.

To run `webserver.py`, type the following in the terminal then hit enter: 

```bash
python3 webserver.py 
```
The terminal will print the hostname as well like server.py did. This is needed for the website and screen craper.


Website
===
The website file is called `index.html`

To load the website, open Chrome browser and type `hostname:8126` in to the address bar. For example: `localhost:8126` if the webserver is listening on `localhost:8126`. 

The website layout is the same and works the same as Saulo's screen_scraper Demo except there is a Show Statistics button at the top right corner of the TreeOne page; clicking the button to show and hide statistics.

Screen Scraper
===
The screen scraperfile is called `screen_scraper.c`

To build the screen scraper, type the following in the terminal then hit enter:

```bash
make
```
To run the screen scraper, type the following in the terminal then hit enter:

```bash
./screen_scraper <host> <port> <username> <filename>
```
Where `host` must be the host the webserver.py is listening on, `port` must be 8126, and `filename` must not on the file list (step 1 would fail since the filename is in the file list).

For example, if `webserver.py` is listening on `localhost` and `test.txt` is a file that does not exist in the file list, a valid command line would be:

```bash
./screen_scraper localhost 8126 user_name test.txt
```
An expected output would be:

```bash
Start screen screaper...
Doing step 1: check if note.txt is already in the list via /api/list.
test.txt is not in the list
Step 1 passed.
Doing step 2: PUSH test.txt.
Step 2 passed.
Doing step 3: verify note.txt was accepted properly via (/api/list).
Step 3 passed.
Doing step 4: test GET without a cookie/authentication
Step 4 passed.
Doing step 5: test POST without a cookie/authentication
Step 5 passed.
Screen scraper finished successfully.
```
Other Files
===
`test.txt`: for screen scraper to test

`Makefile`: for building `screen_scraper.c`
