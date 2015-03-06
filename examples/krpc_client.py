#!/usr/bin/env python3
# -*- coding: utf8 -*-

from krpc.krpc import KRPCClient, KRPCClientException

def main ():
	c = KRPCClient ( "localhost", 8080 )

	# how to pass some parameters to the pre-method hook function
	# (if there's one defined in the server)
	c.set_pre_method_hook_params ( { "counter": 1 } )

	# a normal call
	result = c.echo ( "hello world" )
	print ( result )

	c.set_pre_method_hook_params ( { "counter": 2 } )

	# how to handle an exception
	try:
		c.raise_ioerror ()

	except KRPCClientException as e:
		print ( """
error: %s -> error is ERR_SRV_METHOD_EXCEPTION? %s
message: %s
info: %s""" % ( e.code, e.code == KRPCClientException.ERR_SRV_METHOD_EXCEPTION, e.message, e.info ) )

	# before the "raise_managed" method is called, the pre-method hook
	# method is called with the same parameters as before because here
	# they are not changed.

	# a managed exception
	try:
		result = c.raise_managed ()
		print ( result )

	except KRPCClientException as e:
		print ( "You shouldn't arrive here" )


main ()

