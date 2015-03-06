# KRPC

A JSON-RPC like protocol to create client-server applications with Python 3


## INTRODUCTION

The krpc protocol has been written for the Python3 language. The idea was to have a protocol that was easy to be used also from a web frontend, so it was natural to choose something based on a POST request and on JSON. For Python3 there isn't, as far as I know, a similar thing, so I wrote one from scratch. The krpc protocol is based on the JSON-RPC specification but it differs in some respects:

- it supports file uploads;
- to support file uploads it uses a standard POST request to call a method: the method invocation uses the JSON syntax and is contained in a JSON parameter; the files to be uploaded are contained in the following parts of a multipart message;
- multiple method invocations in the same request are not supported.


## INSTALLATION

The whole implementation is contained in only one file, so you can include it in your projects. However in the package there's the usual setup.py script that installs the file system wide.


## LICENCE

This library is under the GNU LESSER GENERAL PUBLIC LICENSE Version 3. For more information about using/distributing the library see [http://www.gnu.org/copyleft/lesser.html](http://www.gnu.org/copyleft/lesser.html).

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.


## EXAMPLES

Before delving into details it's important to say that if you use Python then all the inner workings are hidden and you call a remote method the same way you call a standard method.

Let's start with the standard "hello world" example. This is a simple client:

	#!/usr/bin/env python3
	# -*- coding: utf8 -*-

	from krpc import KRPCClient, KRPCClientException

	def main ():
		c = KRPCClient ( "localhost", 8080 )

		try:
			result = c.echo ( "hello world" )
			print ( result )

		except KRPCClientException as e:
			print ( "error: %s\nmessage:%s\ninfo:%s\n" % ( e.code, e.message, e.info ) )

	main ()


You connect to a server by creating an instance of the KRPCClient class and specifying the server host and port:

	c = KRPCClient ( "localhost", 8080 )

The remote methods are called as methods of the KRPCClient instance:

	result = c.echo ( "hello world" )

If something goes wrong the KRPCClientException is raised. Its "args" attribute contains the error code, the error message and some additional info (if any).

If one of the method arguments is a file object then the protocol handles the upload to the server in a transparent way and on the server side "appears" a file object pointing to the contents of the uploaded file. There's no limit to the size of the files that can be transferred.

This is all you need to know as far as the client is concerned. And what about the server? This is the server implementing the "echo" method we called in the client:

	#!/usr/bin/env python3
	# -*- coding: utf8 -*-

	from krpc import KRPCServer

	class TestClass ( object ):
		def echo ( self, msg ):
			return msg

	def main ():
		server = KRPCServer ( "localhost", 8080 )

		test_instance = TestClass ()
		server.register_instance ( test_instance )

		print ( 'Starting server, use <Ctrl-C> to stop' )
		#server.serve_forever ()

		quit = False
		while not quit:
			server.handle_request ()

	main ()


To create a server you have to create an instance of the KRPCServer class specifying the host and the port to which clients should connect:

	server = KRPCServer ( "localhost", 8080 )

The server publishes all the methods contained in the object that is passed to the server "register_instance" method:

	server.register_instance ( class_instance )

In the example above the object is an instance of TestClass and this class contains only one method named "echo": this method returns the value passed in the "msg" parameter (well, it's not that useful but it's simple).

The server is started by calling the "serve_forever" method or, if you need more control, by writing a loop in which you call the "handle_request" method that waits until a request is received and handles it. By the way: when a request arrives the server forks a new process to handle it, so requests are handled in parallel.

More documentation is contained in the "docs" directory:

- in the MANUAL file you find the complete description of the Python objects and   how to use them;
- the SPECIFICATION file (to be written) will contain the protocol specification. Because the   protocol is based on a standard multipart/form-data request it should be easy to implement a javascript client, for example, and maybe I'll write one myself in the future.

