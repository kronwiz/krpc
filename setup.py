#!/usr/bin/env python

from distutils.core import setup

setup ( name = 'Krpc',
	version = '1.0',
	description = 'Krpc protocol',
	author = 'Andrea Galimberti',
	author_email = 'andrea.galimberti@gmail.com',
	url = 'https://code.google.com/p/krpc/',
	packages = [ 'krpc' ],

	classifiers = [
		"Development Status :: 5 - Production/Stable",
		"Intended Audience :: Developers",
		"License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
		"Operating System :: OS Independent",
		"Programming Language :: Python :: 3",
		"Topic :: System :: Networking",
		"Topic :: Software Development :: Libraries",
		"Topic :: Internet :: WWW/HTTP :: HTTP Servers"
	]
)
