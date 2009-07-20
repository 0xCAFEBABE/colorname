#!/usr/bin/env python

import sys
import os

from glob import glob
from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES 

import colorname

if os.name == "posix":
	if sys.prefix == "/usr":
		sys.prefix = "/usr/local/"

	for scheme in INSTALL_SCHEMES.values():
		scheme['data'] = scheme['purelib'] 

setup(
	name='colorname',
	version=colorname.__version__,
	author="Philippe 'demod' Neumann & Gina 'foosel' Haeussge",
	author_email='colorname@demod.org',
	url=colorname.__website__,
	description=colorname.__blurb__,
	license=colorname.__licenseName__,
	
	classifiers=[
		"Programming Language :: Python",
		"Development Status :: 5 - Production/Stable",
		"License :: OSI Approved :: GNU General Public License (GPL)",
		"Operating System :: OS Independent",
		"Topic :: Utilities"
	],
	scripts=['colorname.py'],
	data_files=[(colorname.colorDefDir, glob(os.path.join(colorname.colorDefDir, colorname.colorDefPattern)))]
)
