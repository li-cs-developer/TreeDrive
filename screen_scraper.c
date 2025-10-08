#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <stdlib.h>
#include <netdb.h>
#include <assert.h>


const int BUFFER_SIZE = 16384;
int request_size = BUFFER_SIZE;
int response_size = BUFFER_SIZE;
char *host = NULL;      
int port = -1;        
char *username = NULL; 
char *filename = NULL;
char *request = NULL;
char *response = NULL;


//return a malloced char* of given size
char* malloc_char(int size){
    char* chars = malloc(size);
    if(chars == NULL){
        printf("malloc failed\n");
        exit(1);
    }
    return chars;
}


//connect to the host and port in golbal variable and return a socket descriptor
int connect_server(){
    //get host information
    struct hostent *server = gethostbyname(host); 
    if(server == NULL){
        printf("Unable to get host by name\n");
        exit(1);
    }

    // Create socket:
    int socket_desc = socket(AF_INET, SOCK_STREAM, 0);
    if(socket_desc < 0){
        printf("Unable to create socket\n");
        exit(1);
    }

    // Set port and IP the same as server-side:
    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    memcpy(&server_addr.sin_addr.s_addr, server->h_addr, server->h_length);

    // Send connection request to server:
    if(connect(socket_desc, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0){
        printf("Unable to connect\n");
        exit(1);
    }
    return socket_desc;
}


//read data into the global variable char* response from the given socket descriptor
int get_response(int socket_desc){
    //receive data of the header section
    char buffer[BUFFER_SIZE];
    int bytes_received = recv(socket_desc, buffer, BUFFER_SIZE-1, 0);
    if(bytes_received <= 0){
        printf("recv failed\n");
        exit(1);
    }
    buffer[bytes_received] = '\0';

    //find header size
    char *header_end = strstr(buffer, "\r\n\r\n");
    if(!header_end){
        printf("400 Malformed request syntax\n");
        exit(1);
    }
    int header_size = header_end-buffer+4;

    //find the content length
    int content_length = 0;
    char *pointer = strstr(buffer, "Content-Length:");
    if(pointer){
        sscanf(pointer, "Content-Length: %d", &content_length);
    }
    else{
        content_length = bytes_received-header_size;
    }

    //make sure the size of response is large enough
    int total = header_size+content_length;
    if(response_size < total+1){
        free(response);
        response_size = total+1;
        response = malloc_char(response_size);
    }

    //copy everything into response
    memcpy(response, buffer, bytes_received);
    int body_received = bytes_received - header_size;
    while(body_received < content_length){
        int bytes = recv(socket_desc, response+header_size+body_received, content_length-body_received, 0);
        if (bytes <= 0){
            printf("recv failed\n");
            free(response);
            exit(1);
        }
        body_received += bytes;
    }
    response[header_size+content_length] = '\0';

    //return the size of response got
    return header_size+content_length;
}


//search if the global variable filename in the file list return a pointer
char* search_list(){
    //make the LIST request header
    snprintf(request, request_size,
        "GET /api/list HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Cookie: user=%s\r\n"
        "Connection: close\r\n\r\n", host, port, username);
    
    //send the request
    int socket_desc = connect_server();
    send(socket_desc, request, strlen(request), 0);

    //get response
    get_response(socket_desc);
    close(socket_desc);
    
    //return filename pointer
    return strstr(response, filename);
}



int main(int argc, char *argv[]){

    //exit if number arguments != 5 
    if(argc != 5){ 
        printf("Usage: ./a2 <host> <port> <username> <filename>\n");
        printf("Note: <port> of webserver is hard coded to 8126\n");
        exit(1);
    }
    
    //prepare needed variables
    printf("Start screen screaper...\n");
    host = argv[1];
    port = atoi(argv[2]);
    username = argv[3];
    if((argv[4][0]=='"' && argv[4][strlen(argv[4])-1]=='"')||(argv[4][0]=='\'' && argv[4][strlen(argv[4])-1]=='\'')){  
        //if filename is quoted, remove quotes
        memmove(argv[4], argv[4]+1, strlen(argv[4]));
        argv[4][strlen(argv[4])-1] = '\0';
    }
    filename = argv[4];
    request = malloc_char(request_size);
    response = malloc_char(response_size);
    

    //-------------------------------- Step 1 --------------------------------
    printf("Doing step 1: check if %s is already in the list via /api/list.\n", filename);
    if(search_list()){
        printf("%s is already in the server. Please delete it first or change a different file.\n", filename);
        exit(0);
    }
    else{
        printf("%s is not in the list\n", filename);
    }
    printf("Step 1 passed.\n");


    //-------------------------------- Step 2 --------------------------------
    printf("Doing step 2: PUSH %s.\n", filename);

    //open and read the file
    FILE *file = fopen(filename, "rb");
    if(!file){
        printf("Failed to open file %s.\n", filename);
        exit(1);
    }
    fseek(file, 0, SEEK_END);
    long file_size = ftell(file);
    rewind(file);
    char *file_content = malloc_char(file_size);
    fread(file_content, 1, file_size, file);
    fclose(file);

    //make start and end part for body
    char body_start[BUFFER_SIZE];
    const char *boundary = "----boundary";
    int start_length = snprintf(body_start, sizeof(body_start), "--%s\r\n"
        "Content-Disposition: form-data; name=\"filedata\"; filename=\"%s\"\r\n"
        "Content-Type: application/octet-stream\r\n\r\n", boundary, filename);
    char body_end[BUFFER_SIZE];
    int end_length = snprintf(body_end, sizeof(body_end),"\r\n--%s--\r\n", boundary);

    //copy the the start part, file content and end part to into body
    int body_size = start_length + file_size + end_length;
    char *body = malloc_char(body_size);
    memcpy(body, body_start, start_length);
    memcpy(body + start_length, file_content, file_size);
    memcpy(body + start_length + file_size, body_end, end_length);
    free(file_content);

    //make header for PUSH
    snprintf(request, request_size,
        "POST /api/push HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Cookie: user=%s\r\n"
        "Content-Type: multipart/form-data; boundary=%s\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n\r\n", host, port, username, boundary, body_size);

    //send the header and body to the server
    int socket_desc = connect_server();
    send(socket_desc, request, strlen(request), 0);
    send(socket_desc, body, body_size, 0);

    //get and check the response 
    get_response(socket_desc);
    close(socket_desc);
    assert(strstr(response, "200 OK"));
    printf("Step 2 passed.\n");

    
    //-------------------------------- Step 3 --------------------------------
    printf("Doing step 3: verify %s was accepted properly via (/api/list).\n", filename);
    assert(search_list());
    printf("Step 3 passed.\n");

    
    //-------------------------------- Step 4 --------------------------------
    printf("Doing step 4: test GET without a cookie/authentication\n");
    snprintf(request, request_size,
        "GET /api/list HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Connection: close\r\n\r\n", host, port);
    socket_desc = connect_server();
    send(socket_desc, request, strlen(request), 0); 
    get_response(socket_desc);
    close(socket_desc);
    assert(strstr(response, "401 Unauthorized"));
    assert(strstr(response, "Not logged in"));
    printf("Step 4 passed.\n");


    //-------------------------------- Step 5 --------------------------------
    printf("Doing step 5: test POST without a cookie/authentication\n");
    snprintf(request, request_size,
        "POST /api/push HTTP/1.1\r\n"
        "Host: %s:%d\r\n"
        "Content-Type: multipart/form-data; boundary=%s\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n\r\n",
        host, port, boundary, body_size);

    socket_desc = connect_server();
    send(socket_desc, request, strlen(request), 0);
    send(socket_desc, body, body_size, 0);
    get_response(socket_desc);
    close(socket_desc);
    assert(strstr(response, "401 Unauthorized"));
    assert(strstr(response, "Not logged in"));
    printf("Step 5 passed.\n");
    
    
    //clean up
    free(body);
    free(request);
    free(response);
    printf("Screen scraper finished successfully.\n");

    return 0;
}
