Group Chat!
===========

It's like a poor man's Slack.com channel :)

     Author:  Vahid Pazirandeh
     Email:   vpaziran@gmail.com
     Created: July 2013
     Source:  https://github.com/vahidpaz

----

### Usage

First run the server:
> ./server.py

Then connect with a client:
> ./client.py <some_username>

Connect with however many clients you want.

For more info use the `-h` argument.

----

### Notes

##### Security

* No attempts to introduce security have been made. It is likely easy
  for someone to execute shell code in your terminal and root your box. :}

##### Asynchronous

* This app is asynchronous in that each client gets its own thread.

* The Python modules `asyncore`, `asynchat` or a reactive
  programming model are a much better option than the
  network I/O layer created here (polling). However, my goal was
  to gain experience with the low-level socket module and to
  keep things simple.

