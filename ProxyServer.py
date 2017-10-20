# ----------------------------
# 3D3 Proxy Server Project 2
# Name: Rowan Sutton
# Data: 5 April 2017
# Student Number: 13330793
# ----------------------------

from socket import *
import thread

blocked_site_list = []  # List of blocked site names
request_data_cache = {}  # Dictionary to store requests and corresponding data
running = True  # Global variable for exiting the program

# ------------------------------------------------------------------------------------------------------------
#   General use functions
# ------------------------------------------------------------------------------------------------------------


# Given a url, returns the overall domain name, port, IP address, and connection type (http or https)
# Need to deal with www.url.com , http://url.com, http://www.url.com, http://url.com:123, etc
def ip_and_port_from_url(input_url):
    connection_type = "http"  # Default connection type of http
    loc_http = input_url.find("://")  # find where the :// is if there is one
    if loc_http == -1:
        url_no_http = input_url  # no http prefix
    else:
        url_no_http = input_url[(loc_http + 3):]  # get the rest of the url past http://
        connection_type = input_url[:loc_http]  # connection type will be the url prefix http or https
    loc_port = url_no_http.find(":")  # Find the port locaiton
    if loc_port == -1:  # No port number given, use default http of 80
        website_port = 80
        website_name = url_no_http[:len(url_no_http)]
    else:  # We found a port at end of url
        website_port = url_no_http.split(':')[1]  # Should only be one ':' char in url, located before the port number
        website_name = url_no_http[:len(url_no_http) - len(website_port) - 1]  # Url without the port and the ':'
    website_name = website_name.split('/')[0] # Remove subdirectories otherwise DNS lookup will fail
    if str(website_port) == "443":  # Port 443 default for https
        connection_type = "https"
    try:
        website_IP = gethostbyname(website_name)  # DNS lookup
    except:
        website_IP = -1
        print ("DNS LOOKUP FAILURE FOR SITE: " + website_name)
    return website_name, website_port, website_IP, connection_type


# Function for the management console
def management_console():
    print (20 * '-')
    global running  # variable for main thread and management console running
    while running:
        user_choice = raw_input("Type the number of desired operation\n1) Block\n2) Show cache\n3) Exit\n")
        if user_choice == "1":  # Block Site
            fullurl_to_block = raw_input("Enter a site to block: ")
            (site_to_block, port_to_block, ip_to_block, conn_type) = ip_and_port_from_url(fullurl_to_block)
            if ip_to_block in blocked_site_list:  # Blocking by IP
                print (site_to_block + " is already in blacklist")
            elif ip_to_block == -1:
                print ("Site not blocked due to DNS lookup failure")
            else:
                print ("-" * 20)
                print ("url: " + site_to_block)
                print ("port: " + str(port_to_block))
                print ("ip: " + str(ip_to_block))
                print ("connection type: " + conn_type)
                print ("-" * 20)
                blocked_site_list.append(ip_to_block)  # Block by IP address
                print ("Added " + site_to_block + " (" + str(ip_to_block) + ") to blacklist\n")
        elif user_choice == "2":  # Display cache
            print("CACHE LIST:\n\n")
            for x in request_data_cache:  # For each request key in the cache dictionary
                print("[]" * 20 + "\nRequest:\n" + x + "\nData Length: " + str(len(request_data_cache[x])) +
                      "\n" + "[]" * 20 + "\n")
        elif user_choice == "3":  # Exit
            running = False
            print ("\n\nQuitting\n\n")


# This function is to ensure that all of the data that needs to be sent is sent over the socket
def full_send(data_to_send, output_socket):
    overall_amount_sent = 0  # Number of bytes sent already
    while len(data_to_send) > overall_amount_sent:  # number of bytes in data to send > amount sent so far
        if data_to_send:
            current_sent = output_socket.send(data_to_send[overall_amount_sent:])  # send() returns # of bytes sent
            # print("Sent: " + str(current_sent) + " bytes")
            overall_amount_sent = overall_amount_sent + current_sent
        else:
            print("NO DATA TO SEND")
            break

# ------------------------------------------------------------------------------------------------------------
#   Data transfer / socket based functions
# ------------------------------------------------------------------------------------------------------------


# This function is called if a cache hit occurs and sends data from the cache to the browser
def return_cached_data(proxySocket, request):
    print("\tCACHE HIT\n")
    full_send(request_data_cache[request], proxySocket)  # Send data to browser from cache
    print ("Should have sent all data from cache")
    proxySocket.close()  # Done with browser socket


#  This function parses the request and starts either the web server thread or the cache thread
def browser_to_webserver(proxySocket,request):
        requestLineArray = request.split('\n')  # array of sentences separated by '\n' chars
        try:
            full_url = requestLineArray[0].split(' ')[1]  # first line of request, second word
        except:
            print ("\nLess than two word request found\n")
        website_name, website_port, website_IP, connection_type = ip_and_port_from_url(full_url)  # get url params
        if website_IP in blocked_site_list:  # If the website is blocked
            print("Site " + website_name + " is blocked")
            proxySocket.send('<head><body><h1>Blocked by blacklist</h1></body></head>')  # HTML to display
            proxySocket.close()  # Close this socket
        else:
            if request_data_cache.has_key(request):  # Check if cached
                # Cached
                try:
                    thread.start_new_thread(return_cached_data, (proxySocket,request,))  # Thread to get cached data
                    return
                except:
                    print("Failed to spawn thread 'return_cached_data'")
            else:
                # Not Cached
                websiteSocket = socket(AF_INET, SOCK_STREAM)  # Open the proxy to website socket
                print("Site IP Address: " + str(website_IP) + "  Connection type: "
                      + connection_type + "  Port: " + str(website_port))
                websiteSocket.settimeout(5)  # If socket locks up
                websiteSocket.connect((website_IP, int(website_port)))  # Connect from proxy to server
                full_send(request, websiteSocket)  # Send the request on to the webserver
                try:
                    # Start thread to get response from webserver
                    thread.start_new_thread(webserver_back_to_browser, (proxySocket, websiteSocket,request,))
                except:
                    print("Failed to spawn thread 'webserver_back_to_browser'")


# This function transfers data from the webserver back to the browser
def webserver_back_to_browser(proxySocket, websiteSocket,request,):
    full_data_from_site = ""  # Stores all data from site for storage in cache
    while 1:
        try:
            data_from_site = websiteSocket.recv(4096)  # Receive data from the website
        except timeout:
            print("Socket timeout")
            break
        if data_from_site:  # If there is data received
            full_send(data_from_site, proxySocket)  # Send on to the browser
            full_data_from_site = full_data_from_site + data_from_site  # Concatenate to string which stores all data
            request_data_cache[request] = full_data_from_site  # Add all the data received so far to the cache
        else:
            break
    websiteSocket.close()  # This thread is done with its socket resources so close them
    proxySocket.close()


browserPort = 4000  # Set browser port to 4000
serverSocket = socket(AF_INET,SOCK_STREAM)
serverSocket.bind(('', browserPort))
serverSocket.listen(10)  # Listen for 10 connections
print('The server is ready to receive')

thread.start_new_thread(management_console, ())  # Start management console thread

while running:
    connectionSocket, addr = serverSocket.accept()
    sentence = connectionSocket.recv(4096)  # receive request from browser to proxy server
    print(sentence)  # Print the get request through the management console
    # Spawn thread to process the received request
    try:
        thread.start_new_thread(browser_to_webserver, (connectionSocket, sentence,))
    except:
        print("Failed to spawn thread 'browser_to_server'")
print("Closed connection socket proxy to browser")
serverSocket.close()  # Close the browser to proxy socket
