#!/usr/bin/python3

import socket
import json
import sys
import select
import os
import time


HOST = ''   # Symbolic name meaning all available interfaces
PORT = 8125 # 

# Create and configure the server socket
serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
serverSocket.bind((HOST, PORT))
serverSocket.listen()

print(f"TreeDrive server listening on host - {socket.gethostname()} port {PORT}")

myReadables = [serverSocket]  
myWriteables = []            
myClients = []               
usernames = {}  
conn = None
addr = None

while True:
    try:
        
        readable, writeable, exceptions = select.select(
            myReadables + myClients, 
            [], 
            myReadables, 
            5
        )

        for eachSocket in readable:
            if eachSocket is serverSocket:
                # new client

                conn, addr = serverSocket.accept()
                myClients.append(conn)

                #... read handled by select, and ... later
            elif eachSocket in myClients:
                try:
                    data = eachSocket.recv(1024)
                    if data:
                        datastr = data.decode().strip()
                        if eachSocket in usernames:
                            SERVER_FILES = "server_files"
                            os.makedirs(SERVER_FILES, exist_ok=True)
                            SERVER_METADATA = os.path.join(SERVER_FILES, "metadata.json")

                            # process PUSH
                            if datastr.upper().startswith("PUSH"):                     
                                try: 
                                    strings = datastr.split(maxsplit=1)
                                    if len(strings) != 2:
                                        eachSocket.send(b"Usage: PUSH <filename>\n")
                                        continue
                                    
                                    # get needed data of the file
                                    filename = strings[1].strip()
                                    filepath = os.path.join(SERVER_FILES, filename)
                                    eachSocket.send(b"OK") 
                                    size_bytes = eachSocket.recv(16).decode().strip()
                                    fileSize = int(size_bytes)
                                    eachSocket.send(b"OK")

                                    # save the file
                                    with open(filepath, 'wb') as file:
                                        bytesRecvd = 0
                                        while bytesRecvd < fileSize:
                                            oneKB = eachSocket.recv(min(1024, fileSize-bytesRecvd))
                                            if not oneKB:
                                                break
                                            file.write(oneKB)
                                            bytesRecvd += len(oneKB)

                                    # store metadata
                                    metadata = {}
                                    if os.path.exists(SERVER_METADATA):
                                        with open(SERVER_METADATA, "r") as file:
                                            metadata = json.load(file)

                                    metadata[filename] = {
                                        "size": fileSize,
                                        "owner": usernames.get(eachSocket, "---"),
                                        "timestamp": time.ctime()
                                    }

                                    with open(SERVER_METADATA, "w") as file:
                                        json.dump(metadata, file, indent=4)

                                    eachSocket.send(b"File uploaded successfully\n")

                                except Exception as e:
                                    eachSocket.send(f"PUSH failed due to: {e}\n".encode())

                            # process GET
                            elif datastr.upper().startswith("GET"):
                                try: 
                                    #get needed info
                                    strings = datastr.split(maxsplit=1)
                                    if len(strings) != 2:
                                        eachSocket.send(b"Usage: GET <filename>\n")
                                        continue
                                    filename = os.path.basename(strings[1]) 
                                    filepath = os.path.join("server_files", filename)

                                    # sent the file to client
                                    if os.path.exists(filepath):
                                        user = usernames.get(eachSocket, "---")
                                        client_address = eachSocket.getpeername()

                                        fileSize = os.path.getsize(filepath)
                                        eachSocket.send(b"OK\n")

                                        notification = eachSocket.recv(1024).decode().strip()
                                        if notification != "OK":
                                            continue
                                        eachSocket.send(f"{fileSize}\n".encode())

                                        with open(filepath, "rb") as file:
                                            eachSocket.sendall(file.read())
                                        
                                        print(filename)
                                    else:
                                        eachSocket.send(b"File does not exist.\n")

                                except Exception as e:
                                    eachSocket.send(f"GET failed due to: {e}\n".encode())

                            # process LIST
                            elif datastr.upper() == "LIST":
                                try:
                                    # get needed into
                                    if not os.path.exists(SERVER_METADATA):
                                        eachSocket.send(b"No files found in storage.\n")
                                        continue
                                    with open(SERVER_METADATA, "r") as f:
                                        metadata = json.load(f)

                                    # print the list
                                    if metadata:
                                        lines = []
                                        for filename, info in metadata.items():
                                            size = info.get("size", 0)
                                            owner = info.get("owner", "---")
                                            timestamp = info.get("timestamp", "---")
                                            lines.append(f"{filename}\t{size}\t{owner}\t{timestamp}")
                                        response = "\n".join(lines) + "\n"
                                        eachSocket.send(f"{len(response.encode())}\n".encode()) 
                                        eachSocket.send(response.encode())
                                        
                                    else:
                                        eachSocket.send(b"No files found in storage.\n")
                                        
                                except Exception as e:
                                    eachSocket.send(f"LIST failed due to: {e}\n".encode())

                            # process DELETE
                            elif datastr.upper().startswith("DELETE"):
                                try:
                                    # get needed info
                                    strings = datastr.split(maxsplit=1)
                                    if len(strings) != 2:
                                        eachSocket.send(b"Usage: DELETE <filename>\n")
                                        continue
                                    filename = strings[1]
                                    filepath = os.path.join(SERVER_FILES, filename)
                                    metadata = {}
                                    if os.path.exists(SERVER_METADATA):
                                        with open(SERVER_METADATA, "r") as file:
                                            metadata = json.load(file)
                                    
                                    # check if the file exists
                                    if filename not in metadata:
                                        eachSocket.send(b"File not found.\n")
                                        continue

                                    # check file ownership
                                    owner = metadata[filename].get("owner")
                                    currentUser = usernames.get(eachSocket)

                                    if owner != currentUser:
                                        eachSocket.send(b"Permission denied. You are not the owner of this file.\n")
                                        continue

                                    # delete the file
                                    if os.path.exists(filepath):
                                        os.remove(filepath)

                                    del metadata[filename]
                                    with open(SERVER_METADATA, "w") as file:
                                        json.dump(metadata, file, indent=4)
                                    eachSocket.send(b"File deleted.")

                                except Exception as e:
                                    eachSocket.send(f"DELETE failed due to: {e}\n".encode())
                            # invalid commands
                            else:
                                eachSocket.send(b"Invalid command.")


                        else:
                            username = datastr.strip()
                            # remove the client if duplicated uername is used
                            if username in usernames.values():
                                eachSocket.send(f"Username '{username}' is already in use. Pick a different username.\n".encode())
                                myClients.remove(eachSocket)
                                eachSocket.close()
                                continue
                            
                            # login the user
                            else:
                                usernames[eachSocket] = username
                                print(f"New connection from ('{addr[0]}', {addr[1]})")
                                
                                eachSocket.send(f"Logged in as {username}.\n\nAvailable commands: PUSH <file>, GET <file>, LIST, DELETE <file>, ls, cd <path>, QUIT\n".encode()) 
                           
                    else:
                        # close this client....
                        # they are closing on us!
                        print(f"Client ('{addr[0]}', {addr[1]}) disconnected") 
                        if eachSocket in myClients:
                            myClients.remove(eachSocket)
                        if eachSocket in myReadables:
                            myReadables.remove(eachSocket)
                        usernames.pop(eachSocket, None)
                        eachSocket.close()
                        
                except Exception as e:
                    username = usernames.get(eachSocket, "---")
                    if eachSocket in myClients:
                        myClients.remove(eachSocket)
                    if eachSocket in myReadables:
                        myReadables.remove(eachSocket)
                    usernames.pop(eachSocket, None)
                    eachSocket.close()

        for problem in exceptions:
            # ... probably a client socket
            if problem in myClients:
                myClients.remove(problem)
            if eachSocket in myReadables:
                myReadables.remove(eachSocket)
            usernames.pop(problem, None)
            problem.close()

    except KeyboardInterrupt:
        print("Closing the server...")
        sys.exit(0)
    except Exception as e:
        print("The following exception has occured:\n{e}\n")
