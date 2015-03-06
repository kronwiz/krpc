#!/usr/bin/env python3
# -*- coding: utf8 -*-

from krpc.krpc import KRPCServer
import os, time, io


class ServerManagedException ( Exception ):
	managed = True

	def __init__ ( self, code, message, info = "" ):
		self.code = code
		self.message = message
		self.info = info


class TestClass ( object ):
	def echo ( self, msg ):
		return msg

	def raise_ioerror ( self ):
		raise IOError ( "Ooops!" )

	def raise_managed ( self ):
		# you raise it as a normal exception but having a "managed" attribute set to "True"
		# makes the server transform it in a dictionary before returning it to the client
		raise ServerManagedException ( 42, "Answer to the Ultimate Question of Life, the Universe, and Everything" )

	def call_at_every_request ( self, counter ):
		# you'll see this message in the server's log at every request
		print ( "before method: you've called me with counter = %s" % counter )
		# this method shouldn't return anything


def main ():
	server = KRPCServer ( "localhost", 8080 )

	test_instance = TestClass ()
	server.register_instance ( test_instance )
	server.set_pre_method_hook_name ( "call_at_every_request" )

	print ( 'Starting server, use <Ctrl-C> to stop' )
	server.serve_forever ()


main ()

