#-------------------------------------------------------------------------------
# Created:     02/06/2018
# ArcGIS version: 10.3.1
# Python version: 2.7

# Name:        GGL REM Toolbox
# Purpose: Series of tools to build a Relative Elevation Model (REM)
# based on the Geomorphic Grade Line (GGL). 
# Author:      Matt Helstab
#
# Copyright:   (c) jmhelstab 2018
# Licence:     <your licence>
#-------------------------------------------------------------------------------

#Import Modules
import os
import sys
import arcpy
from arcpy.sa import *
import numpy


#Define Toolboxs
class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "GGL REM Toolbox"
        self.alias = "GGLREM"

        # List of tool classes associated with this toolbox
        self.tools = [CrossSections, Centerline, CenterlineStations, REM]

#Create Centerline Feature Class Tool Parameters
class Centerline(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "1. Create a Centerline Feature Class"
        self.description = "Create a polyline Feature Class in the current workspace with expected Fields and Data Types for the Create Cross Section Tool"
        self.canRunInBackground = False

    def getParameterInfo(self):
        workspaceLOC = arcpy.Parameter(
            displayName = "Select Workspace Location",
            name = "WorkspaceLocation",
            datatype = "DEWorkspace",
            parameterType = "Required",
            direction = "Input")
        workspaceLOC.filter.list = ["File System"]

        geodatabaseLOC = arcpy.Parameter(
            displayName = "Select Project Geodatabase",
            name = "geoLocation",
            datatype = "DEWorkspace",
            parameterType = "Required",
            direction = "Input")
        geodatabaseLOC.filter.list = ["Local Database", "Remote Database"]

        centerCOORD = arcpy.Parameter(
            displayName = "Match Coordinate System to LiDAR DEM",
            name = "CoordinateSystem",
            datatype = "GPSpatialReference",
            parameterType = "Required",
            direction = "Input")

        nameFC = arcpy.Parameter(
            displayName = "Output Centerline Feature Class Name",
            name = "CenterlineName",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Output")
        
        params = [workspaceLOC, geodatabaseLOC, centerCOORD, nameFC]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        #Set Local Variables
        ws = parameters[0].valueAsText
        gdb = parameters[1].valueAsText
        DEM = parameters[2].valueAsText
        nameFC = parameters[3].valueAsText
        clName = nameFC + "_Cl"

        #Set Workspace Environment and Map Properties
        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = False
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]

        #Create Feature Class
        arcpy.CreateFeatureclass_management(gdb, clName, "POLYLINE", "", "", "", DEM)

        #Add Route ID Field to Feature Class
        arcpy.AddField_management(clName, "ROUTEID", "TEXT")

        #Add Layers
        Layer_clName = arcpy.mapping.Layer(clName)
        arcpy.mapping.AddLayer(df, Layer_clName)
        
        return

#Create Cross Section Tool Parameters
class CrossSections(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "2. Create Cross Sections"
        self.description = "Create cross section polylines along the valley centerline." 
        self.canRunInBackground = False

    def getParameterInfo(self):
        #First parameter [0]
        inFC = arcpy.Parameter(
            displayName = "Input Centerline Feature Class",
            name = "InputCenterline",
            datatype = ["GPFeatureLayer", "DEFeatureClass", "DEShapefile"],
            parameterType = "Required",
            direction = "Input")

        #Second parameter [1]
        route = arcpy.Parameter(
            displayName = "Select Centerline Route Field",
            name = "RouteName",
            datatype = "Field",
            parameterType = "Required",
            direction = "Input")
        route.filter.list =["TEXT"]
        route.parameterDependencies = [inFC.name]

        #Second parameter [2]
        routeID = arcpy.Parameter(
            displayName = "Select Centerline Route ID",
            name = "RouteID",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
        routeID.filter.type = "ValueList"
        routeID.filter.list = []

        #Second parameter [3]
        offLeft = arcpy.Parameter(
            displayName = "Input Offset Left",
            name = "OffsetLeft",
            datatype = "GPLong",
            parameterType = "Required",
            direction = "Input")
        
        #Third parameter [4]
        offRight = arcpy.Parameter(
            displayName = "Input Offset Right",
            name = "OffsetRight",
            datatype = "GPLong",
            parameterType = "Required",
            direction = "Input")
                    
       #Sixth parameter [4]
        drawDirection = arcpy.Parameter(
            displayName = "Select Direction to Start Stationing From",
            name = "DrawDirection",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
        drawDirection.filter.type = "ValueList"
        drawDirection.filter.list = ["UPPER_LEFT", "UPPER_RIGHT", "LOWER_LEFT", "LOWER_RIGHT"]
        
        params = [inFC, route, routeID, offLeft, offRight, drawDirection]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        if parameters[1].value:  
            with arcpy.da.SearchCursor(parameters[0].valueAsText, parameters[1].valueAsText) as rows:  
                parameters[2].filter.list = sorted(list(set([row[0] for row in rows])))  
        else:  
            parameters[2].filter.list = []
        return

    def updateMessages(self, parameters):
        if parameters[3].altered:
            if parameters[3].value <= 0:
                parameters[3].setErrorMessage('''Offset Value must be greater than zero.''')

        if parameters[4].altered:
            if parameters[4].value >= 0:
                parameters[4].setErrorMessage('''Offset Value must be less than zero.''')

        return

    def execute(self, parameters, messages):

        #Get Parameter Inputs
        fc_in = parameters[0].valueAsText
        route_field = parameters[1].valueAsText
        route_id = parameters[2].valueAsText
        o_left = parameters[3].valueAsText
        o_right = parameters[4].valueAsText
        draw_dir = parameters[5].valueAsText
        length_id = "LOCATION"
        fc_routed = fc_in + "_"  + route_id +"_Routed"
        off_table = "Offset_Table" + "_" + route_id 
        merged = fc_in + "_"  + route_id + "_Merged_Points"
        x_sec = fc_in + "_" + route_id + "_XSections" 
        routesetting = route_field + "POINT" + "LOCATION"
        desc = arcpy.Describe(fc_in)
        gdb = desc.path

        #Set Workspace Environment and Map Properties
        from arcpy import env
        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = False
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]
        
        # Process: Create Routes
        arcpy.CreateRoutes_lr(fc_in, route_field, fc_routed, "LENGTH", "", "", draw_dir, "", "", "IGNORE", "INDEX") 
        
        #Create Table
        arcpy.CreateTable_management(gdb, off_table)

        #Add Fields
        arcpy.AddField_management(off_table, "LOCATION", "LONG")
        arcpy.AddField_management(off_table, "OFFSET_LEFT", "LONG")
        arcpy.AddField_management(off_table, "OFFSET_RIGHT", "LONG")
        arcpy.AddField_management(off_table, route_field, "TEXT")


        #Extract values from Centerline Polyline and create variable with desired row length
        fields_centerline = ['shape_length', 'shape_Length', 'shape_LENGTH', 'Shape_length', 'Shape_Length', 'Shape_LENGTH', 'SHAPE_length', 'SHAPE_Length', 'SHAPE_LENGTH',]
        LOCATION1 = arcpy.da.SearchCursor(fc_routed, fields_centerline,).next()[0]
        LENGTH = int(LOCATION1)
        LOCATION2 = range(1,LENGTH)

        NAME =  arcpy.da.SearchCursor(fc_in, route_field,)  
        NAME = [NAME] * LENGTH

        #Append Extracted Values to Offset_Table
        fields = ["LOCATION", "OFFSET_LEFT", "OFFSET_RIGHT", route_field]
        cursor = arcpy.da.InsertCursor(off_table, fields)
        for x in xrange(1, LENGTH):
            cursor.insertRow((x, o_left, o_right, route_id, ))

        #Process: Make Route Event Layers Left and Right
        arcpy.MakeRouteEventLayer_lr(fc_routed,"ROUTEID",off_table,"ROUTEID POINT LOCATION", "leftoff", "OFFSET_LEFT","NO_ERROR_FIELD","NO_ANGLE_FIELD","NORMAL","ANGLE","LEFT","POINT")
        arcpy.MakeRouteEventLayer_lr(fc_routed,"ROUTEID",off_table,"ROUTEID POINT LOCATION", "rightoff", "OFFSET_RIGHT","NO_ERROR_FIELD","NO_ANGLE_FIELD","NORMAL","ANGLE","LEFT","POINT")

        #Merg#Merge Offset Event Layers

        #arcpy.Merge_management(["leftoff","rightoff"], (os.path.join(sw, merged)), "")
        arcpy.Merge_management(["leftoff","rightoff"], merged, "")

        #Convert Points to Lines
        arcpy.PointsToLine_management(merged, x_sec, "LOCATION", "LOCATION")

        #Add Layers
        Layer_fc_routed = arcpy.mapping.Layer(fc_routed)
        arcpy.mapping.AddLayer(df, Layer_fc_routed)

        Layer_x_sec = arcpy.mapping.Layer(x_sec)
        arcpy.mapping.AddLayer(df, Layer_x_sec)

        arcpy.Delete_management("merged")
        return

# Create Centerline Stations Tool Parameters
class CenterlineStations(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "3. Create Centerline Stations and Table"
        self.description = "Creates a Point Feature Class at each intersection of the Centerline and Cross Section polylines, and then appends elevation data to each point."
        self.canRunInBackground = False

    def getParameterInfo(self):
        #First parameter 
        inFC1 = arcpy.Parameter(
            displayName = "Input Routed Centerline Feature Class",
            name = "InputCenterlineRouted",
            datatype = ["GPFeatureLayer", "DEFeatureClass"],
            parameterType = "Required",
            direction = "Input")
        
        inFC2 = arcpy.Parameter(
            displayName = "Input Cross Section Feature Class",
            name = "InputCrossSection",
            datatype = ["GPFeatureLayer", "DEFeatureClass"],
            parameterType = "Required",
            direction = "Input")
        
        inRASTER = arcpy.Parameter(
            displayName = "Input LiDAR Digital Elevation Model",
            name = "InputLidar",
            datatype = "GPRasterLayer",
            parameterType = "Required",
            direction = "Input")

        params = [inFC1, inFC2, inRASTER]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):

        #Set Local Variables
        centerroute = parameters[0].valueAsText
        crosssection = parameters[1].valueAsText
        raster = parameters[2].valueAsText
        table = parameters[3].valueAsText
        tableName = "GGL_Table"
        stations = crosssection + "_Stations"
        inFeatures = [centerroute, crosssection]
        desc = arcpy.Describe(centerroute)
        gdb = desc.path
        out_table = gdb + "/GGL_Table"

        #Set Workspace Environment and Map Properties
        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = False
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]

        #Creating Centerling Stations Point Feature Class
        arcpy.Intersect_analysis(inFeatures, (os.path.join(gdb, "xsec")), "", "", "POINT")

        arcpy.MultipartToSinglepart_management((os.path.join(gdb, "xsec")), (os.path.join(gdb, "xsec2")))
                
        #Extract elevation data from DEM to Centerline Station Points
        arcpy.sa.ExtractValuesToPoints((os.path.join(gdb, "xsec2")), raster, stations, "INTERPOLATE")

        #REMOVED FOR TESTING POLYNOMIAL CODE BELOW
        #arcpy.Sort_management(stations, "GGL_sorted", [["LOCATION", "ASCENDING"]])
        #arcpy.TableToTable_conversion("GGL_sorted", table, out_table)

        #Delete Unneeded Feature Classes
        arcpy.Delete_management("xsec")
        arcpy.Delete_management("xsec2")
        #arcpy.Delete_management("GGL_sorted")
        
        #Add Layers
        Layer_stations = arcpy.mapping.Layer(stations)
        arcpy.mapping.AddLayer(df, Layer_stations)

        #Centerline Model Building
        ##Extract Values to evalue centelline slope
        px = [row[0] for row in arcpy.da.SearchCursor(stations,"LOCATION")]
        py = [row[0] for row in arcpy.da.SearchCursor(stations,"RASTERVALU")]

        p_2 = numpy.power(px, 2)
        p_3 = numpy.power(px, 3)
        p_4 = numpy.power(px, 4)

        #Linear Model
        polyfit_1 = numpy.polyfit(px, py, 1)
        p1 = numpy.polyval(polyfit_1, px)
        #p1_c1 = polyfit_1[0]
        #p1_b = polyfit_1[1]

        #p1_p1 = numpy.multiply(p1_c1, px)
        #p1 = numpy.add(p1_p1, p1_b)
                
        #Second Order
        polyfit_2 = numpy.polyfit(px, py, 2)
        p2 = numpy.polyval(polyfit_2, px)

        #p2_c2 = polyfit_2[0]
        #p2_c1 = polyfit_2[1]
        #p2_b = polyfit_2[2]
        
        #p2_p2 = numpy.multiply(p2_c2, p_2)
        #p2_p1 = numpy.multiply(p2_c1, px)
        #p_21 = numpy.add(p2_p2, p2_p1)
        #p2 = numpy.add(p_21, p2_b)

        #Third Order
        polyfit_3 = numpy.polyfit(px, py, 3)
        p3 = numpy.polyval(polyfit_3, px)
        
        #p3_c3 = polyfit_3[0]
        #p3_c2 = polyfit_3[1]
        #p3_c1 = polyfit_3[2]
        #p3_b = polyfit_3[3]

        #p3_p3 = numpy.multiply(p3_c3, p_3)
        #p3_p2 = numpy.multiply(p3_c2, p_2)
        #p3_p1 = numpy.multiply(p3_c1, px)
        #p_32 = numpy.add(p3_p3, p3_p2)
        #p_32_1 = numpy.add(p_32, p3_p1)
        #p3 = numpy.add(p_32_1, p3_b)

        #Fourth Order
        polyfit_4= numpy.polyfit(px, py, 4)
        p4 = numpy.polyval(polyfit_4, px)

        #p4_c4 = polyfit_4[0]
        #p4_c3 = polyfit_4[1]
        #p4_c2 = polyfit_4[2]
        #p4_c1= polyfit_4[3]
        #p4_b = polyfit_4[4]

        #p4_p4 = numpy.multiply(p4_c4, p_4)
        #p4_p3 = numpy.multiply(p4_c3, p_3)
        #p4_p2 = numpy.multiply(p4_c2, p_2)
        #p4_p1 = numpy.multiply(p4_c1, px)
        #p_43 = numpy.add(p4_p4, p4_p3)
        #p_43_p2 = numpy.add(p43, p4_p2)
        #p_43_p1 = numpy.add(p_43_p2, p4_p1)
        #p4 = numpy.add(p_43_p1, p4_b)
        
        #Build Structured Array
        ##Set Data Types
        dt = {'names':['LOCATION','LIDAR', 'LINEAR', 'POLY2', 'POLY3', 'POLY4'], 'formats':[numpy.int,numpy.float32, numpy.float32, numpy.float32, numpy.float32, numpy.float32]}

        ##Build Blank Structured Array
        poly = numpy.zeros(len(px), dtype=dt)
        
        ##Add values to Structured Array
        poly['LOCATION'] = px
        poly['LIDAR'] = py
        poly['LINEAR'] = p1
        poly['POLY2'] = p2
        poly['POLY3'] = p3
        poly['POLY4'] = p4

        #Convert Structured Array to Table
        arcpy.da.NumPyArrayToTable(poly, out_table)

        #Join Model Output to Cross Sections and Centerline Stations Feature Classes
        arcpy.JoinField_management(stations, "LOCATION", tableName, "LOCATION", ["LIDAR", "LINEAR", "POLY2", "POLY3", "POLY4"])
        arcpy.JoinField_management(crosssection, "LOCATION", tableName, "LOCATION", ["LIDAR", "LINEAR", "POLY2", "POLY3", "POLY4"])
        return

class REM(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "4. Create Relative Elevation Model"
        self.description = "Joins modeled centelrine eleavtion table to cross sections, converts cross sections to a raster, and subtracts cross section raster from LiDAR raster to produce the REM."
        self.canRunInBackground = False

    def getParameterInfo(self):
        #First parameter 
        inFC = arcpy.Parameter(
            displayName = "Input Cross Section Feature Class",
            name = "InputCrossSections",
            datatype = ["GPFeatureLayer", "DEFeatureClass"],
            parameterType = "Required",
            direction = "Input")

        gglLIST = arcpy.Parameter(
            displayName = "Select Values/Model to Construct Relative Eleavtion Model",
            name = "GglList",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input",
            multiValue = "True")
        gglLIST.filter.type = "ValueList"
        gglLIST.filter.list = ["LiDAR", "Linear Model", "Polynomial 2nd", "Polynomial 3rd", "Polynomial 4th"]
        
        inDEM = arcpy.Parameter(
            displayName = "Input LiDAR DEM",
            name = "InputLidar",
            datatype = ["GPRasterLayer","DERasterDataset", "DERasterCatalog"],
            parameterType = "Required",
            direction = "Input")

        outREM = arcpy.Parameter(
            displayName = "Output Relative Elevation Model(s)",
            name = "OutputREM",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input",
            multiValue = "True")
        outREM.filter.type = "ValueList"
        outREM.filter.list = ["Integer_Meters", "Integer_Decimeters", "Integer_Feet"]

        params = [inFC, gglLIST, inDEM, outREM]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        #Set local variables
        crosssections = parameters[0].valueAsText
        detrend = parameters[1].valueAsText
        lidar = parameters[2].valueAsText
        rems = parameters[3].values
        desc = arcpy.Describe(crosssections)
        gdb = desc.path
        
        #Set Workspace Environment and Map Properties
        arcpy.env.overwriteOutput = True
        arcpy.env.addOutputsToMap = False
        arcpy.env.workspace = gdb
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]

        #REM in Float Meters
        if "LiDAR" in detrend:
                arcpy.PolylineToRaster_conversion(crosssections, "LIDAR", "Centerline", "", "", "1")
                arcpy.Minus_3d(lidar, "Centerline", "Detrended_LiDAR_Float_m")
                if "Integer_Meters" in rems:
                    int_m = Int(Raster("Detrended_LiDAR_Float_m"))
                    int_m.save("Detrended_LiDAR_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer("Detrended_LiDAR_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster("Detrended_LiDAR_Float_m") * 10 ))
                    deci_m.save("Detrended_LiDAR_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer("Detrended_LiDAR_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster("Detrended_LiDAR_Float_m") * 3.28084)
                    int_ft.save("Detrended_LiDAR_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer("Detrended_LiDAR_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
        if "Linear Model" in detrend:
                arcpy.PolylineToRaster_conversion(crosssections, "LINEAR", "Linear", "", "", "1")
                arcpy.Minus_3d(lidar, "Linear", "Detrended_Linear_Float_m")
                if "Integer_Meters" in rems:
                    int_m = Int(Raster("Detrended_Linear_Float_m"))
                    int_m.save("Detrended_Linear_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer("Detrended_Linear_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster("Detrended_Linear_Float_m") * 10 ))
                    deci_m.save("Detrended_Linear_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer("Detrended_Linear_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster("Detrended_Linear_Float_m") * 3.28084)
                    int_ft.save("Detrended_Linear_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer("Detrended_Linear_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
        if "Polynomial 2nd" in detrend:
                arcpy.PolylineToRaster_conversion(crosssections, "POLY2", "Poly2", "", "", "1")
                arcpy.Minus_3d(lidar, "Poly2", "Detrended_Poly2_Float_m")
                if "Integer_Meters" in rems:
                    int_m = Int(Raster("Detrended_Poly2_Float_m"))
                    int_m.save("Detrended_Poly2_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer("Detrended_Poly2_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster("Detrended_Poly2_Float_m") * 10 ))
                    deci_m.save("Detrended_Poly2_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer("Detrended_Poly2_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster("Detrended_Poly2_Float_m") * 3.28084)
                    int_ft.save("Detrended_Poly2_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer("Detrended_Poly2_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
        if "Polynomial 3rd" in detrend:
                arcpy.PolylineToRaster_conversion(crosssections, "POLY3", "Poly3", "", "", "1")
                arcpy.Minus_3d(lidar, "Poly3", "Detrended_Poly3_Float_m")
                if "Integer_Meters" in rems:
                    int_m = Int(Raster("Detrended_Poly3_Float_m"))
                    int_m.save("Detrended_Poly3_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer("Detrended_Poly3_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster("Detrended_Poly3_Float_m") * 10 ))
                    deci_m.save("Detrended_Poly3_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer("Detrended_Poly3_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster("Detrended_Poly3_Float_m") * 3.28084)
                    int_ft.save("Detrended_Poly3_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer("Detrended_Poly3_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)
        if "Polynomial 4th" in detrend:
                arcpy.PolylineToRaster_conversion(crosssections, "POLY4", "Poly4", "", "", "1")
                arcpy.Minus_3d(lidar, "Poly4", "Detrended_Poly4_Float_m")
                if "Integer_Meters" in rems:
                    int_m = Int(Raster("Detrended_Poly4_Float_m"))
                    int_m.save("Detrended_Poly4_Int_m")
                    Layer_GGLREM_Int_M = arcpy.mapping.Layer("Detrended_Poly4_Int_m")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_M)
                if "Integer_Decimeters" in rems:
                    deci_m = (Int(Raster("Detrended_Poly4_Float_m") * 10 ))
                    deci_m.save("Detrended_Poly4_Int_DeciM")
                    Layer_GGLREM_DeciM = arcpy.mapping.Layer("Detrended_Poly4_Int_DeciM")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_DeciM)
                if "Integer_Feet" in rems:
                    int_ft = Int(Raster("Detrended_Poly4_Float_m") * 3.28084)
                    int_ft.save("Detrended_Poly4_Int_Ft")
                    Layer_GGLREM_Int_Ft = arcpy.mapping.Layer("Detrended_Poly4_Int_Ft")
                    arcpy.mapping.AddLayer(df, Layer_GGLREM_Int_Ft)

        #Delete Unneeded Feature Classes
        arcpy.Delete_management("Centerline")
        arcpy.Delete_management("Linear")
        arcpy.Delete_management("Poly2")
        arcpy.Delete_management("Poly3")
        arcpy.Delete_management("Poly4")

        return
    
        