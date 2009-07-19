#!/usr/bin/env python
# -*- coding: utf-8 -*-

## about

name = "colorname"
__blurb__ = "colorname tries to assign a name to a " \
			"color, using predefined color definitions and linear algebra."
__doc__ = __blurb__ + "\n" \
		"For this it calculates the euclidean distance of the currently " \
		"selected color and all predefined colors, " \
		"either in the RGB, HSV, HSL or YIQ color space."

__version__ = "0.3"
__date__ = "19th July 2009"
__website__ = "http://code.foosel.org/colorname"

__author__ = (
	"Philippe 'demod' Neumann (colorname at demod dot org)",
	"Gina 'foosel' Häußge (gina at foosel dot org)" 
)

__licenseName__ = "GPL v2"
__license__ = """This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import sys
import re
import colorsys
import glob
import math
import ConfigParser

import pygtk
pygtk.require('2.0')
import gtk
import gobject

# check gnome
try:
	from gnome import url_show
except ImportError:
	# mock url_show
	def url_show(*args):
		print >>sys.stderr, "gnome bindings not found, can't open URL."

## config

colorDefPattern = "colorname-*.txt"
colorDefDir = "colorname-colors"
windowSize = (350, 600)

class ColorVector(tuple):
	def __sub__(self, v):
		return (self[0] - v[0], self[1] - v[1], self[2] - v[2])

builtinColors = (False, "Builtin colors", 
	{
	 	'Black':		ColorVector([0x00, 0x00, 0x00]),
	 	'Blue':			ColorVector([0x00, 0x00, 0xFF]),
	 	'Green':		ColorVector([0x00, 0xFF, 0x00]),
	 	'Cyan':			ColorVector([0x00, 0xFF, 0xFF]),
	 	'Debian Red':	ColorVector((0xD7, 0x07, 0x51)),
	 	'Red':			ColorVector([0xFF, 0x00, 0x00]),
		'Magenta':		ColorVector([0xFF, 0x00, 0xFF]),
		'Yellow':		ColorVector([0xFF, 0xFF, 0x00]),
		'White':		ColorVector([0xFF, 0xFF, 0xFF])
	}
)

## the code that does the actual work

def hypot(a, b):
	return math.sqrt(a*a + b*b)

def distance(a, b):
	"""	@return: the euclidean distance between the vectors "a" and "b"
		@param a,b: vectors as numpy.array or ColorVector objects
	"""

	return reduce(hypot, a-b)

## GUI code

class GUI:
	## event handlers
	
	def execute(self, widget=False):
		"""execute button event handler"""
		
		foregroundColor = self.getColor()
		self.resultModel.clear()

		# calculate distances and add them to the resultModel
		resultList = []
		for e in filter(lambda x : x[0], self.colorModel):
			(flag, name, colorDict) = e
			distances = calcColorDistances(foregroundColor, colorDict, self.__activeColorSystem)
			
			for dist in distances:
				colorVal = int("%02x%02x%02xff" % tuple(dist[2]), 16)
				resultList.append((dist[0], dist[1], name, colorVal))
				
		resultList.sort()
		map(self.resultModel.append, resultList)
		self.__resultView.scroll_to_point(0, 0)
		self.__resultView.columns_autosize()
				
	def delete_event(self, widget, event, data=None):
		return False

	def destroy(self, widget, data=None):
		gtk.main_quit()

	def __showAbout(self, widget):
		dialog = gtk.AboutDialog()
		
		gtk.about_dialog_set_url_hook(lambda a,b: url_show(b))
		
		dialog.set_name(name)
		dialog.set_authors(__author__)
		dialog.set_comments(__doc__)
		dialog.set_license(__license__)
		dialog.set_version(__version__)
		dialog.set_website(__website__)
		
		dialog.run()
		dialog.destroy()
		
	def __comboboxChangedHandler(self, combobox):
		"""RGB/HSV combobox handler"""
		
		self.__activeColorSystem = combobox.get_active_text()
		
	def __colorlistCheckboxHandler(self, cell, path, model):
		model[path][0] = not model[path][0]

	def __copyColorValHandler(self, widget, colorVal):
		gtk.Clipboard().set_text(("%08X" % colorVal)[:-2])

	def __resultsPopup(self, treeview, event):
		if event.button == 3:
			x = int(event.x)
			y = int(event.y)
			pthinfo = treeview.get_path_at_pos(x, y)
			
			if pthinfo:
				path, col, cellX, cellY = pthinfo
				treeview.grab_focus()
				treeview.set_cursor(path, col, 0)
				
				selection = treeview.get_selection()
				
				if selection:
					(model, iter) = selection.get_selected()
					colorVal = model.get_value(iter, 3)
					
					menu = gtk.Menu()
					
					item = gtk.MenuItem("RGB value: %s" % (("0x%08X" % colorVal)[:-2]))
					item.show()
					menu.append(item)
					
					item = gtk.MenuItem("Copy RGB value to clipboard")
					item.connect("activate", self.__copyColorValHandler, colorVal)
					item.show()
					menu.append(item)
					
					menu.popup(None, None, None, event.button, event.time)
			return 1
				
	def __renderColorPixbuf(self, column, cell, model, iter):
		pixbufSize = 16
		pixbufInnerSize = pixbufSize - 2
		
		# black border
		pixBuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, pixbufSize, pixbufSize)
		pixBuf.fill(0xFF)
		
		# inner color
		subPixBuf = pixBuf.subpixbuf(1, 1, pixbufInnerSize, pixbufInnerSize)
		subPixBuf.fill(model.get_value(iter, 3))
		cell.set_property("pixbuf", pixBuf)

	def getColor(self):
		color = self.colorSelect.get_current_color()
		return ColorVector((color.red / 256, color.green / 256, color.blue / 256))
	
	##

	def __init__(self):
		# color systems
		self.__colorSystems = ["RGB", "HSV", "HSL", "YIQ"]
		self.__activeColorSystem = self.__colorSystems[0]
		
		## main window

		spacing = 5
		self.window = gtk.Window()
		self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		
		self.window.set_default_size(*windowSize)
		
		self.window.set_title("colorname")
		self.window.connect("delete_event", self.delete_event)
		self.window.connect("destroy", self.destroy)
		self.window.set_border_width(1)
		
		pixbuf = self.window.render_icon(gtk.STOCK_SELECT_COLOR, gtk.ICON_SIZE_DIALOG)
		self.window.set_icon(pixbuf)
		
		## main boxes
		
		mainBox = gtk.VBox(spacing=spacing)
		self.window.add(mainBox)
		
		## misc
		
		self.colorSelect = gtk.ColorSelection()
		mainBox.pack_start(self.colorSelect, expand=False)
		
		listsBox = gtk.VPaned()
		listsBox.set_position(150)
		mainBox.pack_start(listsBox, expand=True)

		## colors
		
		colorFrame = gtk.Frame(label="Colors")
		listsBox.pack1(colorFrame, shrink=False)

		colorBox = gtk.VBox(spacing=spacing)
		colorFrame.add(colorBox)

		self.colorModel = gtk.ListStore(gobject.TYPE_BOOLEAN, gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
		colorView = gtk.TreeView(self.colorModel)

		# columns
		toggleRend = gtk.CellRendererToggle()
		toggleRend.set_property('activatable', True)
		toggleRend.connect("toggled", self.__colorlistCheckboxHandler, self.colorModel)

		toggleCol = gtk.TreeViewColumn("", toggleRend)
		toggleCol.add_attribute(toggleRend, "active", 0)
		colorView.append_column(toggleCol)
		colorView.append_column(
			gtk.TreeViewColumn("Colorlist", gtk.CellRendererText(), text=1)
		)
		
		# create scrollbars around the view.
		colorScrolledListView = gtk.ScrolledWindow()
		colorScrolledListView.set_property("hscrollbar_policy", gtk.POLICY_NEVER)
		colorScrolledListView.add(colorView)
		
		colorBox.pack_start(colorScrolledListView)

		## results
		
		resultFrame = gtk.Frame(label="Results")
		listsBox.pack2(resultFrame, shrink=0)

		self.resultModel = gtk.ListStore(gobject.TYPE_FLOAT, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_UINT)
		self.__resultView = gtk.TreeView(self.resultModel)
		self.__resultView.set_search_column(1)
		resultRend = gtk.CellRendererText()

		# color
		colNr=1
		colorCell = gtk.CellRendererPixbuf()
		colorNameCol = gtk.TreeViewColumn("Color")
		colorNameCol.pack_start(colorCell, False)
		colorNameCol.pack_start(resultRend, True)
		colorNameCol.set_sort_column_id(colNr)
		colorNameCol.set_cell_data_func(colorCell, self.__renderColorPixbuf)
		colorNameCol.set_attributes(resultRend, text=colNr)
		self.__resultView.append_column(colorNameCol)
		
		# source
		colNr=2
		sourceCol = gtk.TreeViewColumn("Source", resultRend, text=colNr)
		sourceCol.set_sort_column_id(colNr)
		sourceCol.set_min_width(-1)
		self.__resultView.append_column(sourceCol)
		
		# distance
		colNr=0
		distCol = gtk.TreeViewColumn("Distance", resultRend, text=colNr)
		distCol.set_sort_column_id(colNr)
		distCol.set_sort_order(gtk.SORT_ASCENDING)
		self.__resultView.append_column(distCol)
		
		self.__resultView.connect("button_press_event", self.__resultsPopup)
		
		# create scrollbars around the view.
		resultScrolledListView = gtk.ScrolledWindow()
		resultScrolledListView.set_property("hscrollbar_policy", gtk.POLICY_NEVER)
		resultScrolledListView.add(self.__resultView)
	
		resultFrame.add(resultScrolledListView)
		
		## button box
		
		buttonBox = gtk.HBox(spacing=spacing)
		
		execButton = gtk.Button(stock=gtk.STOCK_EXECUTE)
		execButton.connect("clicked", self.execute)
		buttonBox.pack_start(execButton, fill=False, expand=False)
		
		selCombobox = gtk.combo_box_new_text()
		map(selCombobox.append_text, self.__colorSystems)
		selCombobox.set_active(0)
		buttonBox.pack_start(selCombobox, fill=False, expand=False)
		
		selCombobox.connect("changed", self.__comboboxChangedHandler)
		
		closeButton = gtk.Button(stock=gtk.STOCK_CLOSE)
		closeButton.connect_object("clicked", gtk.Widget.destroy, self.window)
		buttonBox.pack_end(closeButton, fill=False, expand=False)

		aboutButton = gtk.Button("A_bout")
		aboutButton.connect("clicked", self.__showAbout)
		buttonBox.pack_end(aboutButton, fill=False, expand=False)

		mainBox.pack_start(buttonBox, fill=False, expand=False)

		##
		self.window.show_all()
	
	def main(self):
		gtk.main()

## utility functions
		
def parseRgbFromHex(rgbString):
	r = int(rgbString[:2], 16)
	g = int(rgbString[2:4], 16)
	b = int(rgbString[4:6], 16)
	
	return (r, g, b)

def colorParser(configfile):
	parser = ConfigParser.SafeConfigParser()
	parser.optionxform = str;
	parser.read(configfile)
	options = parser.items("options")
	colors = parser.items("colors")
	
	return parseOptions(options), parseColors(colors)

def parseOptions(options):
	optionHash = dict()
	
	for (name, value) in options:
		optionHash[name] = value
		
	return optionHash

def parseColors(colors):
	colorHash = dict()
	
	for (name, value) in colors:
		(r, g, b) = parseRgbFromHex(value)
		colorHash[name] = ColorVector([r, g, b])
		
	return colorHash

def translateColor(color, colorSystem):
	""" Translates the given color in RGB to given color system.
		@param color the color to translate
		@param colorSystem the color system to translate to
		@return the translated color tuple
	"""
	
	if colorSystem == "HSV":
		return rgbToHsv(color)
	elif colorSystem == "YIQ":
		return rgbToYiq(color)
	elif colorSystem == "HSL":
		return rgbToHls(color)
	else:
		return color

def calcColorDistances(color, colorDict, colorSystem):
	""" Calculates the distances of the given color to a dictionary of color definitions in the
		given color system.
		@param color color for which to calculate the distance
		@param colorDict dictionary of name/color pairs against to which calculate the distance
		@param colorSystem color system in which to calculate the distance
		@return a result list containing 3-tuples of distance, name and RGB definition of tested colors
	"""
	
	colornames = dict()
	distances = []
	
	color = translateColor(color, colorSystem)
	
	for (n, c) in colorDict.iteritems():
		listVal = translateColor(c, colorSystem)
		distances.append([distance(color, listVal), n, c])
		
	return distances

def rgbToHsv(color):
	""" Converts the given RGB color to HSV color system. """
	
	r = color[0] / 255.0
	g = color[1] / 255.0
	b = color[2] / 255.0
	
	(h, s, v) = colorsys.rgb_to_hsv(r, g, b)
	return ColorVector((h * 255, s * 255, v * 255))

def rgbToYiq(color):
	""" Converts the given RGB color to YIQ color system. """
	
	r = color[0] / 255.0
	g = color[1] / 255.0
	b = color[2] / 255.0
	
	(y, i, q) = colorsys.rgb_to_yiq(r, g, b)
	return ColorVector((y * 255, i * 255, q * 255))

def rgbToHls(color):
	""" Converts the given RGB color to HLS color system. """
	
	r = color[0] / 255.0
	g = color[1] / 255.0
	b = color[2] / 255.0
	
	(h, l, s) = colorsys.rgb_to_hls(r, g, b)
	return ColorVector((h * 255, l * 255, s * 255))

def loadColors(model, files=None, loadDefault=False):
	""" Loads color definitions from the given list of files and appends them to the given model.
		@param model model to append loaded color definitions to
		@param file list of files from which to load color definitions
		@param loadDefault set to True if builtin colors are to be loaded
		@return False if no files were read in 
	"""
	if loadDefault:
		builtin = list(builtinColors)
		
		# if no other color definitions are loaded
		# => mark the default definitions active
		if not model:
			builtin[0] = True
		
		model.append(builtin)

	if not files:
		return False
	
	for f in files:
		try:
			(optionHash, colorHash) = colorParser(f)
			
			# check if a file with the same name-field has already been loaded
			if filter(lambda x: x[1] == optionHash["name"], model):
				print >>sys.stderr, "Not loading file '%s', colorlist with same name already loaded" % f
				continue
			
			model.append((
				int(optionHash.get("active", True)),
				optionHash["name"],
				colorHash
			))
		except (ValueError, KeyError, ConfigParser.NoSectionError, ConfigParser.ParsingError), e:
			# Note: exception messages don't necessarily make sense
			# Note: OptionParser sucks
			print >>sys.stderr, "Parsing error in file '%s' | %s" % (f, e)

##

def init():
	"""Initializes the GUI and datastructures"""
	
	g = GUI()
	
	## load external color definitions
	pkgdirRe = re.compile("site-packages$")
	
	# color directories
	colorLocations = []
	colorLocations.append(os.path.dirname(sys.argv[0]))
	colorLocations.extend(filter(pkgdirRe.search, sys.path))
	
	tmp = []
	for e in colorLocations:
		tmp.append(os.path.join(e, colorDefDir))
	colorLocations = tmp
	
	# files
	files = []
	for path in colorLocations:
		files.extend(
			glob.glob(os.path.join(path, colorDefPattern))
		)
	
	if files:
		loadColors(g.colorModel, files)
	
	# load default color definitions
	loadColors(g.colorModel, loadDefault=True)
	
	g.execute()
	
	try:
		g.main()
	except KeyboardInterrupt:
		pass
	

if __name__ == '__main__':
	init()
