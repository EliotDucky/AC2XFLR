from scipy.integrate import quad
import xml.etree.ElementTree as el
from matplotlib import pyplot as plt
import numpy as np
import os.path as os_p
from os import makedirs
import math

def createSimpleKVP(key, txt, parent):
	elem = el.Element(key)
	elem.text = txt
	parent.append(elem)
	return elem
	
def createSection(parent, y, c, foil, x_sweep=0.000, dihedral=0.000, twist = 0.000, x_panels = 6, x_distribution="COSINE", y_panels = 9, y_distribution = "INVERSE SINE"):
	
	section = el.Element('Section')
	createSimpleKVP('y_position', str(round(y, 3)), section)
	createSimpleKVP('Chord', str(round(c, 3)), section)
	createSimpleKVP('xOffset', str(round(x_sweep, 3)), section)
	createSimpleKVP('Dihedral', str(round(dihedral, 3)), section)
	createSimpleKVP('Twist', str(round(twist, 3)), section)
	createSimpleKVP('x_number_of_panels', str(x_panels), section)
	createSimpleKVP('x_panel_distribution', x_distribution, section)
	createSimpleKVP('y_number_of_panels', str(y_panels), section)
	createSimpleKVP('y_panel_distribution', y_distribution, section)
	createSimpleKVP('Left_Side_FoilName', foil, section)
	createSimpleKVP('Right_Side_FoilName', foil, section)
	parent.append(section)
	return section

def chordElliptical(y, root_chord, span):
	c = root_chord * (1-(2/span * y)**2)**(1/2)
	return c

def chordRect(y, chord):
	return chord

global_wing_id = -1
def incrimentWingID():
	global global_wing_id
	global_wing_id += 1
	return global_wing_id

class Wing:
	_id = 0
	_type = "mainwing" #"horizontal stabiliser", "vertical stabiliser"
	foil = "NACA 0000" #the name of the foil which must already be instanciated by XFLR
	angle_of_attack = 0.0 #deg
	span = 0.0 #m
	root_chord = 0.0 #m
	mass = 0.0 #kg

	shape = "ellipse"
	fsmf = 0.0 #forward semi-minor fraction for ellipses

	symmetric_fin = False #true if this wing is a fin and symmetrical
	#(reflected along the z axis)
	double_fin = False #true if this wing is a fin and to be doubled
	#(reflected along the y axis)

	chord_func = None #function for calculating chord length at a spanwise position
	chord_params = () #parameters for the chord function other than y

	area = 0.0 #m^2
	aspect_ratio = 0.0

	def __init__(self, foil = "NACA 1212",
		angle_of_attack = 0.0, span = 8.0,
		root_chord = 1.0, mass = 50.0,
		shape_args = {"shape": "ellipse",
			"fsmf": 0.25}, _type = "mainwing",
		symmetric_fin = False,
		double_fin = False,
		draw = False):
		"""
		Use this class to instanciate a wing, tail, or fin.
		Params:
			<string> foil - name of a foil already loaded in XFLR5
			<float> angle_of_attack (deg) - incidence of wing to the horizontal
			<float> span (m) - the span of the entire wing (not semi-wing)
			<float> root_chord (m) - the chord length at the root of the wing
			<float> mass (kg) - the mass of this wing
			<dictionary> shape_args {
				<string> "shape" - the planform shape of the wing
				<float> "fsmf" - only if "shape": "ellipse"
				#MORE SUCH AS TAPER RATIO COMING SOON
			}
			<string> type - can be "mainwing", horizontal stabiliser", "vertical stabiliser"
			<boolean> symmetric_fin - true if this wing is a fin and symmetrical
			<boolean> double_fin - true if this wing is a fin and to be doubled
			<boolean> draw - whether to draw the planform on creation
		"""
		self._id = incrimentWingID()
		self.foil = foil
		self.angle_of_attack = angle_of_attack
		self.span = span
		self.root_chord = root_chord
		self.mass = mass
		self.shape = shape_args["shape"]
		if(self.shape == "ellipse"):
			self.fsmf = shape_args["fsmf"]
			self.chord_func = chordElliptical
			self.chord_params = (self.root_chord, self.span)
		elif(self.shape == "rectangle"):
			self.chord_func = chordRect
			self.chord_params = (self.root_chord,)
		self._type = _type
		self.symmetric_fin = symmetric_fin
		self.double_fin = double_fin

		self.updateAll()
		if(draw):
			self.draw()

	def chordForeElliptical(self, y):
		K_fore = self.root_chord * self.fsmf
		c_fore = K_fore*(1-(2/self.span * y)**2)**0.5
		return c_fore

	def chordAftElliptical(self, y):
		K_aft = self.root_chord * (1-self.fsmf)
		c_aft = K_aft*(1-(2/self.span * y)**2)**0.5
		return -c_aft

	def draw(self):
		ys = []
		c_fores = []
		c_afts = []
		#in independent ifs because number of points needed differs per planform shape
		#rect needs few, elliptical needs many
		if(self.shape == "ellipse"):
			ys = np.linspace(-self.span/2, self.span/2, 200, True)
			c_fores = self.chordForeElliptical(ys)
			c_afts = self.chordAftElliptical(ys)
		elif(self.shape == "rectangle"):
			ys = np.array([-self.span/2, self.span/2])
			c_fores = np.array([0,0])
			c_afts = np.array([-self.root_chord, -self.root_chord])
		plt.figure(figsize=(16, 9), dpi = 80)
		plt.plot(ys, c_fores, label = 'LE')
		plt.plot(ys, c_afts, label = 'TE')
		if(self.span >= self.root_chord):
			lim = self.span/2
		else:
			lim = self.root_chord
		plt.axis([-lim, lim, -lim, lim])
		plt.xlabel('y, span position (m)')
		plt.ylabel('x, longitudinal position (m)')
		plt.title(self._type + " " +str(self._id))
		plt.legend()

	def updateShape(self):
		if(self.shape == "ellipse"):
			self.chord_params = (self.root_chord, self.span)
		elif(self.shape == "rectangle"):
			self.chord_params = (self.root_chord,)

	def updateArea(self):
		if self.chord_params is not None:
			self.area = 2 * quad(self.chord_func, 0, self.span/2, self.chord_params)[0]
		else:
			self.area = 2 * quad(self.chord_func, 0, self.span/2)[0]

	def updateAspectRatio(self):
		#make sure to updateArea before calling this
		self.aspect_ratio = self.span**2 / self.area

	def updateAll(self):
		self.updateShape()
		self.updateArea()
		self.updateAspectRatio()

	#To XML

	def wingToXML(self, resolution=50):
		explane = el.Element('explane')
		explane.set('version', "1.0")

		units = el.SubElement(explane, 'Units')
		ltm = el.SubElement(units, 'length_unit_to_meter')
		ltm.text = '1'
		mtk = el.SubElement(units, 'mass_unit_to_kg')
		mtk.text = '1'
		
		#default mainwing
		selfname = "wing"+str(self._id)
		selfred = '153'
		selfgreen = '254'
		selfblue = '227'
		selftype = 'MAINWING'
		selffin = 'FALSE'
		if(self._type == "horizontal stabiliser"):
			selfname = "horiz"+str(self._id)
			selfred = '20'
			selfgreen = '254'
			selfblue = '227'
			selftype = 'ELEVATOR'
		elif(self._type == "vertical stabiliser"):
			#this is a vert stabiliser
			selfname = "vert"+str(self._id)
			selfred = '254'
			selfgreen = '220'
			selfblue = '20'
			selftype = 'FIN'
			selffin = 'TRUE'
			
		
		wing = el.SubElement(explane, 'wing')
		name = el.SubElement(wing, 'Name')
		name.text = selfname
		_type = el.SubElement(wing, 'Type')
		_type.text = selftype
		color = el.SubElement(wing, 'Color')
		red = el.SubElement(color, 'red')
		red.text = selfred
		green = el.SubElement(color, 'green')
		green.text = selfgreen
		blue = el.SubElement(color, 'blue')
		blue.text = selfblue
		alpha = el.SubElement(color, 'alpha')
		alpha.text = '255'

		pos = el.SubElement(wing, 'Position')
		pos.text = '		  0,		   0,		   0'
		tilt = el.SubElement(wing, 'Tilt_angle')
		tilt.text = '0.000'
		symm = el.SubElement(wing, 'Symetric')
		symm.text = 'true'
		fin = el.SubElement(wing, 'isFin')
		fin.text = selffin
		dbfin = el.SubElement(wing, 'isDoubleFin')
		dbfin.text = str(self.double_fin)
		symfin = el.SubElement(wing, 'isSymFin')
		symfin.text = str(self.symmetric_fin)

		inertia = el.SubElement(wing, 'Inertia')
		volmass = el.SubElement(inertia, 'Volume_Mass')
		volmass.text = str(self.mass)
		
		sections = el.SubElement(wing, 'Sections')
		createSection(sections, 0.000, self.root_chord, self.foil, -self.fsmf*self.root_chord) #root
		dx = self.span/(2*resolution)
		y = dx
		while(y < self.span/2):
			if(self.shape == "ellipse"):
				c = chordElliptical(y, self.root_chord, self.span)
				x_off = self.chordForeElliptical(y)
				if(c == 0.00):
					c = 0.001
			elif(self.shape == "rectangle"):
				c = self.root_chord
				x_off = 0
			createSection(sections, y, c, self.foil, -x_off)
			y+=dx
		#createSection(sections, self.span/2, 0.000, "NACA1212", 0.000, 0.000, 0.000, 13, "COSINE", 5,"UNIFORM") #tip
		save_path = 'geometry'
		if(not os_p.exists(save_path)):
			makedirs(save_path)
		filename = os_p.join(save_path, selfname+'.xml')
		with open(filename, 'wb') as file:
			file.write('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE explane>'.encode('utf-8'))
			el.ElementTree(explane).write(file, encoding='utf-8')
		
		print("Successfully created file "+ selfname +".xml")

	#Getters and Setters
	def getID(self):
		return self._id

	def getFoil(self):
		return self.foil

	def getAngleOfAttack(self):
		return self.angle_of_attack

	def getSpan(self):
		return self.span

	def getRootChord(self):
		return self.root_chord

	def getMass(self):
		return self.mass

	def getShape(self):
		return self.shape

	def getFSMF(self):
		return self.fsmf

	def getChordFunction(self):
		return self.chord_func

	def isSymmetricFin(self):
		return self.symmetric_fin

	def isDoubleFin(self):
		return self.double_fin

	def setFoil(self, foil):
		self.foil = foil

	def setAngleOfAttack(self, angle_of_attack):
		self.angle_of_attack = angle_of_attack

	def setSpan(self, span, draw=False):
		self.span = span
		self.updateAll()

	def setRootChord(self, root_chord, draw=False):
		self.root_chord = root_chord
		self.updateAll()

	def setMass(self, mass):
		self.mass = mass

	def setShape(self, shape, draw=False):
		self.shape = shape
		if(shape == "ellipse"):
			self.chord_func = chordElliptical
		self.updateAll()

	def setFSMF(self, fsmf, draw=False):
		self.fsmf = fsmf

	def setIsSymmetricFin(self, is_symmetric_fin):
		self.symmetric_fin = is_symmetric_fin

	def setIsDoubleFin(self, is_double_fin):
		self.double_fin = is_double_fin

#LIBRARY CREDIT: Michel Robijns
import naca.naca as naca

def coordsToStr(coords):
	x = coords[0]
	x = round(x, 5)
	y = coords[1]
	y = round(y, 5)
	z = coords[2]
	z = round(z, 5)
	_str = str(x) + ", " + str(y) + ", " +str(z)
	return _str
	
def createFuselageFrame(x, y, parent, n=12):
	frame = el.Element('frame')
	
	n /= 2
	n = int(n)
		
	pos = [x, 0, 0]
	pos = coordsToStr(pos)
	createSimpleKVP('Position', pos, frame)
	
	points = []
	theta = math.pi / n
	for i in range(n+1):
		theta = math.pi / n
		theta *= i
		_sin = y * math.sin(theta)
		_cos = y * math.cos(theta)
		point = [x, _sin, _cos]
		point = coordsToStr(point)
		createSimpleKVP('point', point, frame)

	parent.append(frame)
	
	return frame

class Fuselage:
	foil = "NACA "
	fuse2d = [] #coords for entire 2d surface
	suction = [] #coords for top surface
	pressure = []
	chord = 0
	
	def __init__(self, naca_4, chord, N=24):
		self.fuse2d = naca.NACA4(naca_4, N)
		LE_index = int(len(self.fuse2d)/2) + 1
		self.pressure = self.fuse2d[LE_index:len(self.fuse2d)]
		self.suction = self.fuse2d[0:LE_index]
		self.foil += naca_4
		self.chord = chord
		
	def checkPayloadGeo(self, radius_h, radius_v, t_loc, top_taller = True, plot = False):
		"""
		<radius_h> = horizontal length occupied by payload forwards of thickest payload point
		<radius_v> = vertical height occupied by payload upwards of fuselage datum line
		<t_loc> = location of thickest payload geo as fraction of chord from LE
		[top_taller] = does payload stick out more at top or bottom
		
		returns: True if fuselage doesn't collide with payload
		"""
		surf = self.suction
		if(not top_taller):
			surf = self.pressure
			
		fore_x = t_loc - radius_h / self.chord
		y = radius_v / self.chord
		aft_x = t_loc + radius_h / self.chord
		
		if(plot):
			plt.figure(figsize=(16, 9), dpi = 80)
			xs = []
			ys = []
			for i in range(len(surf)):
				xs.append(surf[i][0])
				ys.append(surf[i][1])
				
			#box
			plx = []
			ply = []
			
			plx.append(fore_x)
			ply.append(0)
			
			plx.append(fore_x)
			ply.append(y)
			
			plx.append(aft_x)
			ply.append(y)
			
			plx.append(aft_x)
			ply.append(0)
			
			plt.plot(xs, ys)
			plt.plot(plx, ply, 'r')
			plt.ylim(0, 0.5)
		
		legal = True
		
		for coords in surf:
			if(coords[0] < t_loc):
				if(coords[0] > fore_x and coords[1] < y):
					legal = False
					break
			elif(coords[0] > t_loc):
				if(coords[0] < aft_x and coords[1] < y):
					legal = False
					break
		
		return legal

	def fuselageToXML(self):
		"""
		Frames must be written before degrees otherwise will crash on import to XFLR
		"""
		explane = el.Element('explane')
		explane.set('version', "1.0")
		
		units = el.SubElement(explane, 'Units')
		ltm = el.SubElement(units, 'length_unit_to_meter')
		ltm.text = '1'
		mtk = el.SubElement(units, 'mass_unit_to_kg')
		mtk.text = '1'
		
		body = el.SubElement(explane, 'body')
		name = el.SubElement(body, 'Name')
		name.text = "Fuselage " + self.foil
		color = el.SubElement(body, 'Color')
		red = el.SubElement(color, 'red')
		red.text = '98'
		green = el.SubElement(color, 'green')
		green.text = '102'
		blue = el.SubElement(color, 'blue')
		blue.text = '156'
		alpha = el.SubElement(color, 'alpha')
		alpha.text = '255'
		
		desc = el.SubElement(body, 'Description')
		desc.text = 'fuselage'
		pos = el.SubElement(body, 'Position')
		pos.text = '0, 0 ,0'
		_type = el.SubElement(body, 'Type')
		_type.text = 'FLATPANELS'
		inertia = el.SubElement(body, 'Inertia')
		vmass = el.SubElement(inertia, 'Volume_Mass')
		vmass.text = '0.000'
			
		for i in range(len(self.suction)):
			x = self.suction[-i][0] * self.chord
			y = self.suction[-i][1] * self.chord
			createFuselageFrame(x, y, body, 18)
			
		xdeg = el.SubElement(body, 'x_degree')
		xdeg.text  = '3'
		hoop_deg = el.SubElement(body, 'hoop_degree')
		hoop_deg.text = '4'
		xpanels = el.SubElement(body, 'x_panels')
		xpanels.text = '19'
		hoop_panels = el.SubElement(body, 'hoop_panels')
		hoop_panels.text = '11'

		selfname = str(name.text) + ".xml"
		save_path = 'geometry'
		if(not os_p.exists(save_path)):
			makedirs(save_path)
		filename = os_p.join(save_path, selfname)
			
		with open(filename, 'wb') as file:
			file.write('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE explane>'.encode('utf-8'))
			el.ElementTree(explane).write(file, encoding='utf-8')
			
		print("Successfully created file "+ selfname)