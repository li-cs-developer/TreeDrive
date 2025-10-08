#!/usr/bin/python3

import socket
import sys
import re        
import json
import time      
import traceback 
import threading


SERVER_HOST = '' # please hard code it to where server.py is listening on
SERVER_PORT = 8125 # port of server.py
HOST = ''  # Symbolic name meaning all available interfaces
PORT = 8126 # port of webserver.py
stats = {} # for /api/stats



def send_response(client, status, body, content_type="text/html", cookies=None):
    # process body
    if isinstance(body, dict):
        body = json.dumps(body)
        content_type = "application/json"
        body = body.encode('utf-8')
    elif not isinstance(body, bytes):
        body = body.encode('utf-8')

    # process header
    header = [f"HTTP/1.1 {status}", f"Content-Type: {content_type}", f"Content-Length: {len(body)}", "Connection: close"]
    if cookies:
        for key, value in cookies.items():
            header.append(f"Set-Cookie: {key}={value}; Path=/")
    header = "\r\n".join(header + ["", ""]).encode('utf-8')

    # send response
    client.sendall(header + body)



# get filename from url by converting hex to ascii after %
def get_filename(path):

    # do the conversion if file= is found
    found = re.search(r"file=([^&]+)", path)
    if found:
        string = found.group(1).replace('+', ' ')
        filename = ""
        pos = 0
        while pos < len(string):

            # look for % from position 0 to string.length-2
            if string[pos] == '%' and pos < len(string)-2:

                # add the converted 2 chars after % if no error
                try:
                    num = string[pos+1:pos+3]
                    filename += chr(int(num, 16))
                    pos += 3

                # add % if the conversion failed
                except ValueError:
                    filename += string[pos]
                    pos += 1

            # add the character to filename if not %
            else:
                filename += string[pos]
                pos += 1

        return filename
    
    # return none if no match
    else: 
        return None    


def run_client(client):
    try:
        # get data before body part
        data = b''
        while b"\r\n\r\n" not in data: 
            chunk = client.recv(1024)
            if not chunk:
                break
            data += chunk

        if not data:
            client.close()
            return

        # process header
        header_end = data.find(b"\r\n\r\n")
        if header_end == -1:
            send_response(client, "400 Bad Request", {"status": "error", "message": "Malformed request syntax"})
            return
        else:
            headers_section = data[:header_end].decode(errors='ignore')
            lines = headers_section.split("\r\n")
            request = lines[0]
            method, path, _ = request.split(" ", 2)
            headers = {}
            for line in lines[1:]:
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    headers[key.lower()] = value
        
        # get body part data
        body_part = data[header_end + 4:]
        content_length = int(headers.get("content-length", 0))
        while len(body_part) < content_length:
            chunk = client.recv(1024)
            if not chunk:
                break
            body_part += chunk

        # get username
        username = None
        cookies = headers.get("cookie", "")
        lines = cookies.split(";")
        cookies = {} 
        for line in lines:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                cookies[key] = value
        username = cookies.get("user")

        # process API paths under GET method
        if method == "GET":

            # load the webpage
            if path == '/' :
                try:
                    with open("index.html", "rb") as file:
                        webpage = file.read()
                    send_response(client, "200 OK", webpage, content_type="text/html")
                except FileNotFoundError:
                    send_response(client, "404 Not Found", b"webpage is not found", content_type="text/plain")

            # get a list of all files in the FileSharing
            elif path == "/api/list":

                # Only users who are logged in (with cookies) should be able to do anything with the system (list, get, push, delete)
                if not username:
                    message = '{"error": "Not logged in"}'
                    send_response(client, "401 Unauthorized", {"status": "error", "message": message})
                    return
                
                # send LIST command to server
                with socket.create_connection((SERVER_HOST, SERVER_PORT)) as s:

                    # login and request LIST
                    s.sendall(f"{username}\n".encode())
                    s.recv(1024)  
                    s.sendall(b"LIST\n")
                    
                    # get size of metadata
                    size = b""
                    while not size.endswith(b"\n"):
                        byte = s.recv(1)
                        if not byte:
                            break
                        size += byte
                    size = int(size.decode().strip())

                    # get metadata 
                    data = ""
                    received_bytes = 0
                    while received_bytes < size:
                        chunk = s.recv(1024).decode()
                        if not chunk:
                            break
                        data += chunk
                        received_bytes += 1024

                    # format metadata
                    file_list = []
                    for line in data.strip().splitlines():
                        metadata = line.split("\t")
                        if len(metadata) == 4:
                            file_list.append({"name": metadata[0], "size": round(int(metadata[1])/1048576, 7), "owner": metadata[2], "timestamp": metadata[3]})

                    # send response 
                    send_response(client, "200 OK", {"status": "ok", "files": file_list})

            # Download the file specified
            elif path.startswith("/api/get"):

                # Only users who are logged in (with cookies) should be able to do anything with the system (list, get, push, delete)
                if not username:
                    message = '{"error": "Not logged in"}'
                    send_response(client, "401 Unauthorized", {"status": "error", "message": message})
                    return

                # get filename
                filename = get_filename(path)
                if not filename:
                    send_response(client, "400 Bad Request", {"status": "error", "message": "Malformed request syntax"})
                    return

                with socket.create_connection((SERVER_HOST, SERVER_PORT)) as s:
                    # login
                    s.sendall(f"{username}\n".encode())
                    s.recv(1024)
                    
                    # send GET command to the server
                    start_time = time.time()
                    s.sendall(f"GET {filename}\n".encode())
                    response = s.recv(1024).strip()

                    # respond 404 Not Found if file not found
                    if response != b"OK":
                        message = '"error": "File not found"'
                        send_response(client, "404 Not Found", {"status": "error", "message": message})
                        return
                    s.sendall(b"OK\n")  

                    # receive file content
                    file_size = int(s.recv(1024).decode().strip())
                    received_bytes = b""
                    while len(received_bytes) < file_size:
                        chunk = s.recv(min(1024, file_size-len(received_bytes)))
                        if not chunk:
                            break
                        received_bytes += chunk
                    time_used = time.time()-start_time

                # make HTTP header
                headers = {
                    "Content-Type": "application/octet-stream",
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Length": str(len(received_bytes)),
                    "Connection": "close"
                }
                response = "HTTP/1.1 200 OK\r\n"
                for key, value in headers.items():
                    response += f"{key}: {value}\r\n"
                response += "\r\n"

                # send the header and file
                client.sendall(response.encode() + received_bytes)

                # keep track time used and count
                if filename not in stats:
                    stats[filename] = {"count": 0, "time": 0}
                stats[filename]["count"] += 1
                stats[filename]["time"] += time_used

            # Return statistics of the number of downloads each file had in the web server and the average time to fulfill those requests.
            elif path == "/api/stats":
               
                # Only users who are logged in (with cookies) should be able to do anything with the system (list, get, push, delete)
                if not username:
                    message = '{"error": "Not logged in"}'
                    send_response(client, "401 Unauthorized", {"status": "error", "message": message})
                    return

                # make stats response
                statistics = {}
                for filename, data in stats.items():
                    avg_time = data["time"]/data["count"] if data["count"]>0 else 0
                    statistics[filename] = {"number of downloads": data["count"],"average time": avg_time}
  
                send_response(client, "200 OK", {"status": "ok", "stats": statistics})

            # respond 404 Not Found if api path is not valid
            else:
                send_response(client, "404 Not Found", b"no such API path", content_type="text/plain")

        # process API paths under POST method
        elif method == "POST":

            # process form base on content type
            content_type = headers.get('content-type', '')
            form = {}

            # default
            if 'application/x-www-form-urlencoded' in content_type:
                body_part = body_part.decode()
                for pair in body_part.split('&'):
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        form[key] = value.replace('+', ' ')

            # for upload file
            elif 'multipart/form-data' in content_type:
                boundary = content_type.split("boundary=")[-1].encode()
                try:
                    file_part = body_part.split(b"--" + boundary)[1]
                    header, _, file_content = file_part.partition(b"\r\n\r\n")
                    found = re.search(b'filename="([^"]+)"', header)
                    if found:
                        form['filename'] = found.group(1).decode()
                        form['filedata'] = file_content.rstrip(b"\r\n--")
                except Exception:
                    send_response(client, "400 Bad Request", {"status": "error", "message": "Malformed request syntax"})
                    return   
                
            # respond error if other content types
            else:
                send_response(client, "415 Unsupported Media Type", {"status": "error", "message": "Missing or Invalid content type"})
                return

            # Log into the system, return a 200, and sets cookies
            if path == "/api/login":

                # get username
                username = form.get("username", "").strip()
                if not username:
                    send_response(client, "400 Bad Request", {"status": "error", "message": "Malformed request syntax"})
                    return
                
                # login to server
                with socket.create_connection((SERVER_HOST, SERVER_PORT)) as s:
                    s.sendall(f"{username}\n".encode())
                    reply = s.recv(1024).decode()
                    if reply.startswith("Logged in as"):
                        send_response(client, "200 OK", {"status": "ok", "message": reply.strip()}, cookies={"user": username})
                    else:
                        message = f'"error": "Login failed"'
                        send_response(client, "500 Internal Server Error", {"status": "error", "message": message})

            # Upload a new file on the server
            elif path.startswith("/api/push"):

                # Only users who are logged in (with cookies) should be able to do anything with the system (list, get, push, delete)
                if not username:
                    message = '{"error": "Not logged in"}'
                    send_response(client, "401 Unauthorized", {"status": "error", "message": message})
                    return
                
                # send error response if needed parts are not in the form
                elif "filename" not in form or "filedata" not in form:
                    send_response(client, "400 Bad Request", {"status": "error", "message": "Malformed request syntax"})
                    return
                
                # get needed data and connect to the server
                filename = form["filename"]
                filedata = form["filedata"]
                with socket.create_connection((SERVER_HOST, SERVER_PORT)) as s:

                    # login to the server and send PUSH 
                    s.sendall(f"{username}\n".encode())
                    s.recv(1024)
                    s.sendall(f"PUSH {filename}\n".encode())

                    # send error response if expected notification is not received
                    if s.recv(1024).strip() != b"OK":
                        message = '{"status": "Upload failed"}'
                        send_response(client, "500 Internal Server Error", {"status": "error", "message": message})
                        return

                    # send file size to the server
                    s.sendall(f"{len(filedata)}\n".encode())

                    # send error response if expected notification is not received
                    if s.recv(1024).strip() != b"OK":
                        message = '{"status": "Upload failed"}'
                        send_response(client, "500 Internal Server Error", {"status": "error", "message": message})
                        return

                    # push the file
                    print(f"Pushing {filename}")
                    s.sendall(filedata)

                    # send different responses depend on the server's reply
                    reply = s.recv(1024).decode()
                    if reply == "File uploaded successfully\n":
                        message = '{"status": "File uploaded"}'
                        send_response(client, "200 OK", {"status": "ok", "message": message})
                    else:
                        message = '{"status": "Upload failed"}'
                        send_response(client, "500 Internal Server Error", {"status": "error", "message": message})


            # respond 404 Not Found if api path is not valid
            else:
                send_response(client, "404 Not Found", b"no such API path", content_type="text/plain")

        # process API paths under DELETE method
        elif method == "DELETE":

            # Delete the specified file from the system
            if path.startswith("/api/delete"):

                # Only users who are logged in (with cookies) should be able to do anything with the system (list, get, push, delete)
                if not username:
                    message = '{"error": "Not logged in"}'
                    send_response(client, "401 Unauthorized", {"status": "error", "message": message})
                    return
                
                # find filename from query string and decode it 
                filename = get_filename(path)

                # send DELETE command to server
                with socket.create_connection((SERVER_HOST, SERVER_PORT)) as s:

                    # login to the server and send DELETE command
                    s.sendall(f"{username}\n".encode())
                    s.recv(1024)
                    s.sendall(f"DELETE {filename}\n".encode())
                    reply = s.recv(1024).decode().strip()

                    # send different responses depend on the server's relies
                    message = '{"error": "Delete failed"}'
                    if reply == "File deleted.":
                        message = '{"status": "File deleted"}'
                        send_response(client, "200 OK", {"status": "ok", "message": message})
                    elif reply == "File not found.":
                        send_response(client, "404 Not Found", {"status": "error", "message": message})
                    elif reply == "Permission denied. You are not the owner of this file.":
                        send_response(client, "401 Unauthorized", {"status": "error", "message": message})
                    else:
                        send_response(client, "500 Internal Server Error", {"status": "error", "message": message})

               
            # Log out of the system
            elif path == "/api/login":
                send_response(client, "200 OK", {"status": "ok", "message": "Logged out"}, cookies={"user": ""})

            # respond 404 Not Found if api path is not valid
            else:
                send_response(client, "404 Not Found", b"no such API path", content_type="text/plain")

    # print where is wrong and send server error response
    except Exception as e:
        traceback.print_exc()
        send_response(client, "500 Internal Server Error", {"status": "error", "message": str(e)})

    # close TCP connection
    finally:
        client.close()


# main program here
try:
    # start multi-threaded server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Web server listening on host - {socket.gethostname()} port {PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=run_client, args=(conn,), daemon=True).start()

# print message and exist if Control C is pressed
except KeyboardInterrupt:
    print("\tClosing the webserver...")
    sys.exit(0)
