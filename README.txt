Multi-User Group Chat Program!

     Author: Vahid Pazirandeh
      Email: vpaziran@gmail.com
 Start Date: July 2013
     GitHub: https://github.com/vahidpaz

################################################################################

HOW TO RUN:

> ./server.py -h

To run client:
> ./client.py -h

################################################################################

NOTES:

* No attempts to introduce security have been made. It is likely easy
  for someone to execute shell code in your terminal and root your box. :}

* The Python modules asyncore and asynchat are much more sophisticated than
  the network I/O layer being used here. However my goal was to play
  with the socket module and I wanted a multi-threaded app.

