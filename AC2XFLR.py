from scipy.integrate import quad
import xml.etree.ElementTree as el
from matplotlib import pyplot as plt
import numpy as np
import os.path as os_p
from os import makedirs

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
			ys = np.linspace(-self.span/2, self.span, 200, True)
			c_fores = self.chordForeElliptical(ys)
			c_afts = self.chordAftElliptical(ys)
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


	def updateArea(self):
		self.area = 2 * quad(self.chord_func, 0, self.span/2, (self.root_chord, self.span))[0]

	def updateAspectRatio(self):
		#make sure to updateArea before calling this
		self.aspect_ratio = self.span**2 / self.area

	def updateAll(self):
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

