#!/usr/bin/env python
# -*- coding: utf-8 -*-

## about

name = "colorname"
__blurb__ = "colorname tries to assign a name to a " \
			"color, using predefined color definitions and linear algebra."
__doc__ = __blurb__ + "\n" \
		"For this it calculates the euclidean distance of the currently " \
		"selected color and all predefined colors, " \
		"either in the RGB or HSV color space."

__version__ = "0.2rc2"
__date__ = "8th August 2007"
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

# start in gimp or in stand-alone mode?
try:
	import gimp
	import gimpfu
	from gimpplugin import plugin as GimpPlugin
except ImportError, e:
	if not "-gimp" in sys.argv:
		# standalone
		gimp = False
		# mock GimpPlugin
		GimpPlugin = object
	else:
		print >>sys.stderr, "Aborting. Error loading gimp python modules: %s" % e
		sys.exit(-1)


## config

location = "<Toolbox>/Xtns/_Colorname"
colorDefPattern = "colorname-*.txt"
colorDefDir = "colorname-colors"

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

windowSizes = {
	"gimp": (350, 350),
	"standalone": (350, 600)
}


## the code that does the actual work

def hypot(a, b):
	return math.sqrt(a*a + b*b)

def distance(a, b):
	"""	@return: the euclidean distance between the vectors "a" and "b"
		@param a,b: vectors as numpy.array or ColorVector objects
	"""

	return reduce(hypot, a-b)

## ApiWrapper template

class ApiWrapper:
	def getColor(self):
		pass
	
	def setColor(self):
		pass

class GimpWrapper(ApiWrapper):
	def getColor(self):
		return ColorVector(gimp.get_foreground())
	
	def setColor(self, r, g, b):
		gimp.set_foreground(r, g, b)

class StandaloneWrapper(ApiWrapper):
	def getColor(self):
		color = self.colorSelect.get_current_color()
		return ColorVector((color.red / 256, color.green / 256, color.blue / 256))
	
	def setColor(self, r, g, b):
		colorDef = "#%02x%02x%02x" % (r, g, b)
		self.colorSelect.set_current_color(gtk.gdk.color_parse(colorDef))

## GUI code

class GUI:
	## event handlers
	
	def execute(self, widget=False):
		"""execute button event handler"""
		
		foregroundColor = wrapper.getColor()
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

	def __addFiles(self, widget):
		"""colorlist adding dialog0"""
		
		buttons = (
			gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
			gtk.STOCK_OK, gtk.RESPONSE_ACCEPT
		)
		dialog = gtk.FileChooserDialog(buttons=buttons)
		dialog.set_action(gtk.FILE_CHOOSER_ACTION_OPEN)
		dialog.set_select_multiple(True)
	
		filterColor = gtk.FileFilter()
		filterColor.set_name("color definitions")
		filterColor.add_pattern("*.txt")
		dialog.add_filter(filterColor)
	
		filterAll = gtk.FileFilter()
		filterAll.set_name("everything")
		filterAll.add_pattern("*")
		dialog.add_filter(filterAll)
	
		response = dialog.run()
		
		if response == gtk.RESPONSE_ACCEPT:
			files = dialog.get_filenames()
			if files:
				loadColors(self.colorModel, files)

		dialog.destroy()
			
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
		
	def __comboboxChangedHandler(self, widget):
		"""RGB/HSV combobox handler"""
		
		## FIXME: might work or not depending on the libgtk version
		#num = widget.get_active()
		#self.__activeColorSystem = widget.get_model()[num][0]
		
		## workaround
		if self.__activeColorSystem == self.__colorSystems[0]:
			self.__activeColorSystem = self.__colorSystems[1]
		else:
			self.__activeColorSystem = self.__colorSystems[0]	
		
	def __colorlistCheckboxHandler(self, cell, path, model):
		model[path][0] = not model[path][0]

	def __resultsDoubleclickHandler(self, treeview, path, view_column):
		treeview.grab_focus()
		treeview.set_cursor(path, view_column, 0)
		
		selection = treeview.get_selection()
		if selection:
			(model, iter) = selection.get_selected()
			colorVal = model.get_value(iter, 3)
			self.__setColorValHandler(None, colorVal)
		
	def __setColorValHandler(self, widget, colorVal):
		(r, g, b) = parseRgbFromHex("%08x" % colorVal)
		wrapper.setColor(r, g, b)
		
	def __copyColorValHandler(self, widget, colorVal):
		gtk.Clipboard().set_text(("%08X" % colorVal)[:-2])

	def __colorsPopup(self, treeview, event):
		if event.button == 3:
			self.colorMenu.popup(None, None, None, event.button, event.time)
			return 1

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
					
					if gimp:
						item = gtk.MenuItem("Set as foreground color")
						item.connect("activate", self.__setColorValHandler, colorVal)
						item.show()
						menu.append(item)
					
					item = gtk.MenuItem("Copy RGB value to clipboard")
					item.connect("activate", self.__copyColorValHandler, colorVal)
					item.show()
					menu.append(item)
					
					menu.popup(None, None, None, event.button, event.time)
			return 1
				
	def __renderColorPixbuf(self, column, cell, model, iter):
		# black border
		pixbufSize = 16
		pixbufInnerSize = pixbufSize -2
		
		pixBuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, pixbufSize, pixbufSize)
		pixBuf.fill(0xFF)
		
		# inner color
		subPixBuf = pixBuf.subpixbuf(1, 1, pixbufInnerSize, pixbufInnerSize)
		subPixBuf.fill(model.get_value(iter, 3))
		cell.set_property("pixbuf", pixBuf)

	##

	def __init__(self):
		# color systems
		self.__colorSystems = ["RGB", "HSV"]
		self.__activeColorSystem = self.__colorSystems[0]
		
		## main window

		spacing = 5
		self.window = gtk.Window()
		self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
		
		if gimp:
			self.window.set_default_size(*windowSizes["gimp"])
		else:
			self.window.set_default_size(*windowSizes["standalone"])
		
		self.window.set_title("colorname")

		self.window.connect("delete_event", self.delete_event)
		self.window.connect("destroy", self.destroy)
		self.window.set_border_width(1)
		
		## main boxes
		
		mainBox = gtk.VBox(spacing=spacing)
		self.window.add(mainBox)

		## standalone
		
		if not gimp:
			wrapper.colorSelect = gtk.ColorSelection()
			mainBox.pack_start(wrapper.colorSelect, expand=False)
		
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
		
		self.colorMenu = gtk.Menu()
		addItem = gtk.MenuItem("Add")
		addItem.connect("activate", self.__addFiles)
		addItem.show()
		self.colorMenu.append(addItem)
		
		colorView.connect("button_press_event", self.__colorsPopup)

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
		self.__resultView.connect("row-activated", self.__resultsDoubleclickHandler)
		
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
		
		selCombobox.connect_object("changed", self.__comboboxChangedHandler, selCombobox)
		
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

def calcColorDistances(color, colorDict, colorSystem):
	colornames = dict()
	distances = []
	
	if colorSystem == "HSV":
		color = rgbToHsv(color)
	
	for (n, c) in colorDict.iteritems():
		if colorSystem == "HSV":
			listVal = rgbToHsv(c)
		else:
			listVal = c
		
		distances.append([distance(color, listVal), n, c])
		
	return distances

def rgbToHsv(color):
	r = color[0] / 255.0
	g = color[1] / 255.0
	b = color[2] / 255.0
	
	(h, s, v) = colorsys.rgb_to_hsv(r, g, b)
	return ColorVector((h * 255, s * 255, v * 255))

def loadColors(model, files=None, loadDefault=False):
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

## gimp plugin class

class Colorname(GimpPlugin):
	def query(self):
		"""	pygimp_install_procedure(PyObject *self, PyObject *args) {
				[...]
				PyObject *pars, *rets;
				
				if (!PyArg_ParseTuple(args, "sssssszziOO:install_procedure",
					&name, &blurb, &help,
					&author, &copyright, &date, &menu_path, &image_types,
					&type, &pars, &rets))
		"""
		
		copyright = re.subn(
			"('.*?' )|( \(.*?\))",
			"",
			" & ".join(__author__)
		)[0]
		
		gimp.install_procedure (
			'plug_in_colorname',	# name
			__blurb__,				# blurb
			__doc__,				# help
			", ".join(__author__),	# author
			copyright,				# copyright
			__date__,				# date
			location,				# menu_path
			'',						# image_types
			gimpfu.PLUGIN,			# type
			((gimpfu.PF_INT, 'run_mode', "interactive"),),	# pars
			()						# rets
		)

	def plug_in_colorname(self, *args):
		init()

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
	if gimp:
		wrapper = GimpWrapper()
		Colorname().start()
	else:
		wrapper = StandaloneWrapper()
		init()
