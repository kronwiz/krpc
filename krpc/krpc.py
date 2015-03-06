#!/usr/bin/env python3
# -*- coding: utf8 -*-

# LICENSE
# 
# This library is copyright by Andrea Galimberti <andrea.galimberti@gmail.com>.
# This library is under the GNU LESSER GENERAL PUBLIC LICENSE Version 3. For
# more information about using/distributing the library see
# http://www.gnu.org/copyleft/lesser.html.
# 
# The above copyright notice, the licence and the following disclaimer shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.

from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ForkingMixIn
import os, cgi, urllib, json, traceback
import urllib.request, time, random, io
import mimetypes, tempfile


CRLF = "\r\n"
CHUNK_SIZE = 8192

class KHTTPServer ( ForkingMixIn, HTTPServer ): pass

class KRequestHandlerException ( Exception ): pass

# {{{ KRPCClientException
class KRPCClientException ( Exception ):
	# Server errors
	# -------------
	# pre-defined errors
	ERR_SRV_INVALID_REQUEST = -32600
	ERR_SRV_JSON_DECODING = -32700
	ERR_SRV_METHOD_NOT_FOUND = -32601
	# custom-errors (reserved range: -32000, -32099)
	ERR_SRV_METHOD_EXCEPTION = -32000
	ERR_SRV_UNHANDLED_EXCEPTION = -32001
	ERR_SRV_MISSING_FILE_OBJECT = -32002
	ERR_SRV_JSON_ENCODING = -32003

	# Client errors
	# -------------
	ERR_REQUEST = 10000
	ERR_CONNECTION_REFUSED = 10001
	ERR_JSON_PARSE = 10002

	MESSAGES = {
		# server errors
		ERR_SRV_INVALID_REQUEST: "Invalid request.",
		ERR_SRV_JSON_DECODING: "Parse error.",
		ERR_SRV_METHOD_NOT_FOUND: "Method not found.",
		ERR_SRV_METHOD_EXCEPTION: "Method call raised an exception.",
		ERR_SRV_UNHANDLED_EXCEPTION: "Unhandled exception.",
		ERR_SRV_MISSING_FILE_OBJECT: "Missing file object.",
		ERR_SRV_JSON_ENCODING: "Object is not JSON serializable.",

		# client errors
		ERR_REQUEST: "Request error",
		ERR_CONNECTION_REFUSED: "Connection refused",
		ERR_JSON_PARSE: "Error parsing JSON"
	}

	def __init__ ( self, code, msg = None, info = None ):
		self.code = code

		if not msg:
			msg = self.MESSAGES.get ( self.code, "" )

		self.message = msg
		self.info = info


	def __str__ ( self ):
		txt = "%s (%s)" % ( self.msg, self.code )
		if self.info: txt = "%s: %s" % ( txt, self.info )
		return txt
# }}}
# {{{ KFieldStorage
class KFieldStorage ( cgi.FieldStorage ):
	def getfile ( self, key, default = None ):
		if key in self:
			value = self[key]
			if isinstance( value, list ):
				return value[0].file
			else:
				return value.file
		else:
			return default
# }}}
# {{{ KRequestArgs
class KRequestArgs ( object ):
	def __init__ ( self ):
		self.method_name = None
		self.params = None
		self.pre_method_hook_params = None
# }}}
# {{{ KRequestHandler
class KRequestHandler ( BaseHTTPRequestHandler ):

	def extract_json ( self, params ):
		if not "json" in params:
			if not "JSON" in params:
				self.send_error ( 400, "Missing 'json' parameter" )
				return None

			else:
				param_json = params [ "JSON" ]

		else:
			param_json = params [ "json" ]

		if isinstance ( param_json, list ): param_json = param_json [ 0 ]
		if isinstance ( param_json, ( cgi.MiniFieldStorage, cgi.FieldStorage ) ): param_json = param_json.value
		return param_json


	def send_data ( self, stream ):
		buf = stream.read ( CHUNK_SIZE )
		while buf:
			if not isinstance ( buf, bytes ): buf = bytes ( buf, "utf8" )
			self.wfile.write ( buf )
			buf = stream.read ( CHUNK_SIZE )


	def send_json ( self, data ):
		try:
			body = json.dumps ( data )

		except TypeError as e:
			raise KRequestHandlerException ( KRPCClientException.ERR_SRV_JSON_ENCODING, e.args [ 0 ] )

		self.wfile.write ( bytes ( body, "utf8" ) )


	def send_json_error ( self, err_code, err_info = None ):
		if not self.headers_sent:
			self.send_header ( "Content-Type", "application/json" )
			self.end_headers ()
			self.headers_sent = True

		error = { "error": { "code": err_code, "message": KRPCClientException.MESSAGES [ err_code ] } }
		if err_info: error [ "error" ] [ "info" ] = err_info
		self.send_json ( error )


	def send_json_result ( self, res ):
		data = { "result": res }
		self.send_json ( data )


	def send_result ( self, res ):
		if isinstance ( res, io.IOBase ):
			self.send_header ( "Content-Type", "application/octet-stream" )

		else:
			self.send_header ( "Content-Type", "application/json" )

		self.end_headers ()
		self.headers_sent = True

		if isinstance ( res, io.IOBase ):
			self.send_data ( res )

		else:
			self.send_json_result ( res )


	def reinstate_files ( self, params, form ):
		if isinstance ( params, list ):
			items = enumerate ( params )

		elif isinstance ( params, dict ):
			items = params.values ()

		for k, v in items:
			if v.startswith ( "__file__:" ):
				f = form.getfile ( v )

				if f:
					params [ k ] = f

				else:
					raise KRequestHandlerException ( KRPCClientException.ERR_SRV_MISSING_FILE_OBJECT, v )


#	def get_method_name_and_params ( self, json_req, form = None ):
#		method = None
#		params = None
#
#		try:
#			req = json.loads ( json_req )
#
#		except ValueError:
#			raise KRequestHandlerException ( KRPCClientException.ERR_SRV_JSON_DECODING )
#
#		method = req.get ( "method" )
#		params = req.get ( "params" )
#
#		if not isinstance ( method, str ): method = str ( method )
#
#		# re-inserts the uploaded files (if any) in the appropriate places
#		if form: self.reinstate_files ( params, form )
#
#		return method, params


	def decode_request ( self, json_req, form = None ):
		args = KRequestArgs ()

		try:
			req = json.loads ( json_req )

		except ValueError:
			raise KRequestHandlerException ( KRPCClientException.ERR_SRV_JSON_DECODING )

		args.method_name = req.get ( "method" )
		args.params = req.get ( "params" )
		args.pre_method_hook_params = req.get ( "pmhparams" )

		if not isinstance ( args.method_name, str ): args.method_name = str ( args.method_name )

		# re-inserts the uploaded files (if any) in the appropriate places
		if form: self.reinstate_files ( args.params, form )

		return args


	def find_method ( self, method_path ):
		obj = self.server.instance

		try:
			for p in method_path.split ( "." ):
				obj = getattr ( obj, p )

		except AttributeError:
			obj = None

		return obj


	def call_method ( self, method_name, params ):
		#method_name, params = self.get_method_name_and_params ( json_req, form )
		if not method_name:
			raise KRequestHandlerException ( KRPCClientException.ERR_SRV_INVALID_REQUEST, "Method not specified." )

		method = self.find_method ( method_name )

		if ( not method ) or ( not callable ( method ) ):
			raise KRequestHandlerException ( KRPCClientException.ERR_SRV_METHOD_NOT_FOUND )

		if not params: params = []
		if not isinstance ( params, ( list, dict ) ): params = [ params ]

		try:
			if isinstance ( params, list ):
				res = method ( *params )

			elif isinstance ( params, dict ):
				res = method ( **params )

		except Exception as e:
			if getattr ( e, "managed", False ) == True:
				res = { "error": { "code": getattr ( e, "code", -1 ), "message": getattr ( e, "message", "" ) } }
				if hasattr ( e, "info" ): res [ "error" ] [ "info" ] = e.info

			else:
				raise KRequestHandlerException ( KRPCClientException.ERR_SRV_METHOD_EXCEPTION, traceback.format_exc () )

		return res


	def handle_request ( self, param_json, form = None ):
		self.headers_sent = False
		self.send_response ( 200 )

		args = self.decode_request ( param_json, form )

		try:
			if self.server.pre_method_hook_name:
				self.call_method ( self.server.pre_method_hook_name, args.pre_method_hook_params )

			res = self.call_method ( args.method_name, args.params )
			if not res: res = {}

			self.send_result ( res )

		except KRequestHandlerException as e:
			self.send_json_error ( *e.args )

		except:
			self.send_json_error ( KRPCClientException.ERR_SRV_UNHANDLED_EXCEPTION, traceback.format_exc () )


	def do_GET ( self ):
		params = urllib.parse.parse_qs ( urllib.parse.urlparse ( self.path ).query )
		param_json = self.extract_json ( params )
		if param_json == None: return
		self.handle_request ( param_json )


	def do_POST ( self ):
		# Parse the form data posted
		form = KFieldStorage ( 
			fp = self.rfile,
			headers = self.headers,
			environ = {
				'REQUEST_METHOD': 'POST',
				'CONTENT_TYPE': self.headers['Content-Type'],
			} )

		param_json = self.extract_json ( form )
		if param_json == None: return
		self.handle_request ( param_json, form )
# }}}
# {{{ KRPCServer
class KRPCServer ( KHTTPServer ):
	def __init__ ( self, host, port ):
		super ( KHTTPServer, self ).__init__ ( ( host, port ), KRequestHandler )

		self.instance = None
		self.pre_method_hook_name = None


	def register_instance ( self, instance ):
		self.instance = instance


	def set_pre_method_hook_name ( self, name ):
		self.pre_method_hook_name = name
# }}}
# {{{ KRPCClientMethod
class KRPCClientMethod ( object ):
	def __init__ ( self, client, name ):
		self.client = client
		self.name = name


	def __getattr__ ( self, name ):
		return KRPCClientMethod ( self.client, '.'.join ( ( self.name, name ) ) )


	def __call__ ( self, *args, **kwargs ):
		return self.client.execute ( self.name, *args, **kwargs )
# }}}
# {{{ KRPCClient
class KRPCClient ( object ):
	MULTIPART_BOUNDARY = "-----KrOnOsThEwIzArD"

	def __init__ ( self, server_name, server_port ):  # ( str, int )
		self.server_name = server_name
		self.server_port = server_port
		self.files = None
		self.pre_method_hook_params = None


	def __getattr__ ( self, name ):
		return KRPCClientMethod ( self, name )


	def execute ( self, method_name, *args, **kwargs ):
		self.files = {}

		params = []
		items = []

		if len ( args ):
			params = list ( args )
			items = enumerate ( args )

		elif len ( kwargs ):
			params = kwargs
			items = params.values ()

		for k, v in items:
			if hasattr ( v, "read" ):
				uname = self.generate_unique_name ()
				self.files [ uname ] = v
				params [ k ] = uname

		data = { "method": method_name, "params": params, "pmhparams": self.pre_method_hook_params }
		params_json = json.dumps ( data )

		multipart = False
		content_length = 0

		if len ( self.files ):
			content_length, body = self.build_multipart ( params_json )
			multipart = True

		else:
			body = params_json

		try:
			res = self.send_request ( body, content_length, multipart )

		except urllib.error.URLError as e:
			raise KRPCClientException ( KRPCClientException.ERR_REQUEST, info = "errno: %s, strerror: %s" % ( e.args [ 0 ].errno, e.args [ 0 ].strerror ) )

		return res


	def get_data ( self, stream ):
		fh, fname = tempfile.mkstemp ( prefix = "krpctemp" )
		buf = stream.read ( CHUNK_SIZE )
		try:
			while buf:
				os.write ( fh, buf )
				buf = stream.read ( CHUNK_SIZE )

		finally:
			os.close ( fh )

		return open ( fname, 'r' )


	def send_request ( self, body, content_length, multipart ):
		req = urllib.request.Request ( "http://%s:%s" % ( self.server_name, self.server_port ) )

		if not multipart:
			body = bytes ( urllib.parse.urlencode ( { "json": body } ), "utf8" )

		else:
			req.add_header ( "Content-Type", "multipart/form-data; boundary=%s" % self.MULTIPART_BOUNDARY )
			req.add_header ( "Content-Length", content_length )

		req.add_data ( body )

		fin = urllib.request.urlopen ( req )

		content_type = fin.info ().get ( "Content-Type", "application/json" )

		if content_type == "application/octet-stream":
			result = self.get_data ( fin )

		else:
			res = fin.read ()
			fin.close ()
			result = self.parse_result ( res, fin.info () )

		return result


	def parse_result ( self, data, info ):
		data = data.decode ( "utf8" )

		#print ( "DATA: %s" % data )
		#print ( "INFO: %s" % info.items () )

		try:
			data = json.loads ( data )

		except ValueError as e:
			raise KRPCClientException ( KRPCClientException.ERR_JSON_PARSE, info = str ( e ) )

			# NON DOVREBBE PIU' PRESENTARSI PERCHE' RISOLTO LATO SERVER
			# It seems there are cases in which the returned json is contained in
			# the info part of the response. Don't know why it happens: it's just
			# when there are runtime errors due to programming errors in the server
			# part, e.g.: NameError.
			#try:
			#	data = json.loads ( info )

			#except ValueError as e:
			#	raise KRPCClientException ( KRPCClientException.ERR_JSON_PARSE, info = str ( e ) )

		if "result" in data:
			return data [ "result" ]

		elif "error" in data:
			error = data [ "error" ]
			raise KRPCClientException ( error [ "code" ], error [ "message" ], error.get ( "info" ) )


	def generate_unique_name ( self ):
		r = "%s-%s" % ( time.time (), random.random () )
		return "__file__:%s" % r


	def body_generator ( self, params_json ):
		buf = "--%s%s" % ( self.MULTIPART_BOUNDARY, CRLF )
		buf += 'Content-Disposition: form-data; name="json"%s%s' % ( CRLF, CRLF )
		buf += "%s%s" % ( params_json, CRLF )

		yield bytes ( buf, "utf8" )

		for uname, stream in self.files.items ():
			# fsize = os.stat ( stream.name ).st_size
			fname = os.path.basename ( stream.name )
			content_type = mimetypes.guess_type ( fname ) or "application/octet-stream"
			# the stream is always re-opened in binary mode: in this way the "read"
			# method returns always a bytes instance, thus avoiding encoding errors.
			full_path = stream.name
			stream.close ()
			stream = open ( full_path, 'rb' )

			buf = "--%s%s" % ( self.MULTIPART_BOUNDARY, CRLF )
			buf += 'Content-Disposition: form-data; name="%s"; filename="%s"%s' % ( uname, fname, CRLF )
			buf += 'Content-Type: %s%s%s' % ( content_type, CRLF, CRLF )

			yield bytes ( buf, "utf8" )

			buf = stream.read ( CHUNK_SIZE )
			while buf:
				if not isinstance ( buf, bytes ): buf = bytes ( buf, "utf8" )
				yield buf
				buf = stream.read ( CHUNK_SIZE )

			yield bytes ( CRLF, "utf8" )

		yield bytes ( "--%s--%s%s" % ( self.MULTIPART_BOUNDARY, CRLF, CRLF ), "utf8" )


	def build_multipart ( self, params_json ):
		cl = len ( "--%s%s" % ( self.MULTIPART_BOUNDARY, CRLF ) )
		cl += len ( 'Content-Disposition: form-data; name="json"%s%s' % ( CRLF, CRLF ) )
		cl += len ( "%s%s" % ( params_json, CRLF ) )

		for uname, stream in self.files.items ():
			fsize = os.stat ( stream.name ).st_size
			fname = os.path.basename ( stream.name )
			content_type = mimetypes.guess_type ( fname ) or "application/octet-stream"

			cl += len ( "--%s%s" % ( self.MULTIPART_BOUNDARY, CRLF ) )
			cl += len ( 'Content-Disposition: form-data; name="%s"; filename="%s"%s' % ( uname, fname, CRLF ) )
			cl += len ( 'Content-Type: %s%s%s' % ( content_type, CRLF, CRLF ) )

			cl += fsize
			cl += len ( CRLF )

		cl += len ( "--%s--%s%s" % ( self.MULTIPART_BOUNDARY, CRLF, CRLF ) )

		return cl, self.body_generator ( params_json )


	def set_pre_method_hook_params ( self, params ):
		self.pre_method_hook_params = params
# }}}

