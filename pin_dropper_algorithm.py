# -*- coding: utf-8 -*-

"""
/***************************************************************************
 pin_dropper
                                 A QGIS plugin
 Drops pins
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2020-09-29
        copyright            : (C) 2020 by Joshua Evans
        email                : joshuaevanslowell@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'Joshua Evans'
__date__ = '2020-10-6'
__copyright__ = '(C) 2020 by Joshua Evans'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from random import randint
import math
import numpy as np
import itertools
from time import time
from osgeo import gdal

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterString,
                       QgsProcessingParameterBoolean,
                       QgsWkbTypes,
                       QgsFields,
                       QgsField,
                       QgsFeature,
                       QgsGeometry,
                       QgsProject,
                       QgsCoordinateTransform,
                       QgsPoint,
                       QgsPointXY,
                       QgsRectangle,
                       QgsVectorLayer
                       # QgsRasterPipe,
                       # QgsRasterFileWriter,
                       )

class PinDropperAlgorithm(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    #basics
    OUTPUT = 'OUTPUT'
    RASTER_INPUT = 'RASTER_INPUT'
    BOUND_BOX_INPUT = 'BOUND_BOX_INPUT'
    # row and point interval
    ROW_VECTOR_INPUT = 'R0W_VECTOR_INPUT'
    ROW_HEIGHT_INPUT = 'ROW_HEIGHT_INPUT'
    ROW_HEIGHT_STDEV_INPUT = 'ROW_HEIGHT_STDEV_INPUT'
    POINT_INTERVAL_INPUT = 'POINT_INTERVAL_INPUT'
    POINT_INTERVAL_STDEV_INPUT = 'POINT_INTERVAL_STDEV_INPUT'
    #overlay for comparisons between plants
    OVERLAY_BOX_RADIUS_INPUT = 'OVERLAY_BOX_RADIUS_INPUT'
    OVERLAY_BOX_SAMPLING_INPUT = 'OVERLAY_BOX_SAMPLING_INPUT'
    OVERLAY_MATCH_THRESHOLD_MIN_INPUT = 'OVERLAY_MATCH_THRESHOLD_MIN_INPUT'
    #parameters for searching for overlay matches
    SEARCH_NUM_ITERATIONS_INPUT = 'SEARCH_NUM_ITERATIONS_INPUT'
    SEARCH_ITERATION_SIZE_INPUT = 'SEARCH_ITERATION_SIZE_INPUT'
    ASSUME_EMPTIES_INPUT = 'ASSUME_EMPTIES_INPUT'
    #output field name
    FIELD_NAME_INPUT = 'FIELD_NAME_INPUT'



    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # raster layer. repeating pattern in the raster will be used to drop pins
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.RASTER_INPUT,
                self.tr('Raster Layer'),
                [QgsProcessing.TypeRaster]
            )
        )
        # bounding box
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.BOUND_BOX_INPUT,
                self.tr('Bounding Box'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        #field name
        self.addParameter(
            QgsProcessingParameterString(
                self.FIELD_NAME_INPUT,
                self.tr('Output Field Name'),
                defaultValue="data"
            )
        )

        # direction vector for rows
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.ROW_VECTOR_INPUT,
                self.tr('Row Vector'),
                [QgsProcessing.TypeVectorLine],
            )
        )

        # row height
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ROW_HEIGHT_INPUT,
                self.tr('Row Height'),
                type=QgsProcessingParameterNumber.Double,
                minValue=0
            )
        )

        # point interval
        self.addParameter(
            QgsProcessingParameterNumber(
                self.POINT_INTERVAL_INPUT,
                self.tr('Point Interval'),
                type=QgsProcessingParameterNumber.Double,
                minValue=0
            )
        )

        # overlay box radius
        self.addParameter(
            QgsProcessingParameterNumber(
                self.OVERLAY_BOX_RADIUS_INPUT,
                self.tr('Overlay Box Radius'),
                minValue=0,
                defaultValue=2
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.OVERLAY_MATCH_THRESHOLD_MIN_INPUT,
                self.tr("Overlay Box Threshold"),
                type=QgsProcessingParameterNumber.Double,
                minValue=0,
                maxValue=1,
                defaultValue=.66,  # this number has absolutely no scientific or mathematical basis
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ASSUME_EMPTIES_INPUT,
                self.tr("Assume Empty Positions"),
                defaultValue=False
            )
        )

        #optional parameters
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ROW_HEIGHT_STDEV_INPUT,
                self.tr('Row Height Stdev'),
                type=QgsProcessingParameterNumber.Double,
                minValue=0,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.POINT_INTERVAL_STDEV_INPUT,
                self.tr('Point Interval Stdev'),
                type=QgsProcessingParameterNumber.Double,
                minValue=0,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.OVERLAY_BOX_SAMPLING_INPUT,
                self.tr('Overlay Box Resolution'),
                type=QgsProcessingParameterNumber.Integer,
                minValue=0,
                defaultValue=16

            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.SEARCH_ITERATION_SIZE_INPUT,
                self.tr("Search Iteration Size"),
                type=QgsProcessingParameterNumber.Integer,
                minValue=2,
                defaultValue=5
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.SEARCH_NUM_ITERATIONS_INPUT,
                self.tr("Number of Search Iterations"),
                type=QgsProcessingParameterNumber.Integer,
                minValue=1,
                defaultValue=2
            )
        )

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )


    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        # declare algorithm parameters, mainly just so we have them all in on place
        self._root = None
        self._bound_box = None
        self._defined_points = {}
        self._loose_ends = None
        self.row_h_geo_dx = 0
        self.row_h_geo_dy = 0
        self.col_w_geo_dx = 0
        self.col_w_geo_dy = 0
        self.col_w_stdev = .1
        self.row_h_stdev = .1
        self.overlay_box_radius = 0

        # read parameters

        # required parameters
        self.raster = self.parameterAsRasterLayer(parameters, self.RASTER_INPUT, context)
        self._bound_box = self.parameterAsVectorLayer(parameters, self.BOUND_BOX_INPUT, context)
        self.overlay_box_radius = self.parameterAsDouble(parameters, self.OVERLAY_BOX_RADIUS_INPUT, context)
        self.col_w = self.parameterAsDouble(parameters, self.POINT_INTERVAL_INPUT, context)
        self.row_h = self.parameterAsDouble(parameters, self.ROW_HEIGHT_INPUT, context)
        row_vector = self.parameterAsVectorLayer(parameters, self.ROW_VECTOR_INPUT, context)

        # optional parameters
        row_h_stdev = self.parameterAsDouble(parameters, self.ROW_HEIGHT_STDEV_INPUT, context)
        point_interval_stdev = self.parameterAsDouble(parameters, self.POINT_INTERVAL_STDEV_INPUT, context)
        self.overlay_box_sampling = self.parameterAsInt(parameters, self.OVERLAY_BOX_SAMPLING_INPUT, context)
        self.overlay_match_min_threshold = self.parameterAsDouble(parameters, self.OVERLAY_MATCH_THRESHOLD_MIN_INPUT, context)
        self.search_iter_count = self.parameterAsInt(parameters, self.SEARCH_NUM_ITERATIONS_INPUT, context) - 1
        self.search_iter_size = self.parameterAsInt(parameters, self.SEARCH_ITERATION_SIZE_INPUT, context)
        self.assume_empties = self.parameterAsBool(parameters, self.ASSUME_EMPTIES_INPUT, context)

        assert self.search_iter_size % 2 == 1, "Search iteration size should be odd to include search centerpoint."

        field_name = self.parameterAsString(parameters, self.FIELD_NAME_INPUT, context)

        # handle box radius and box sampling
        self.overlay_box_radius += .5

        # Compute the number of steps to display within the progress bar and
        other_attrs = [field_name] # todo: spec this in csv
        attrs = ['row', 'col', *other_attrs]
        out_fields = QgsFields()
        # x and y indexes
        out_fields.append(QgsField(name=attrs[0], type=QVariant.Int))
        out_fields.append(QgsField(name=attrs[1], type=QVariant.Int))
        out_fields.append(QgsField(name=attrs[2], type=QVariant.Double))

        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the procedxssAlgorithm function.
        (self._sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields=out_fields,
            geometryType=QgsWkbTypes.Point,
            crs=self._bound_box.crs())

        # convert row vector to the same CRS as the bounding box
        row_vector_geom = list(row_vector.getFeatures())[0].geometry()
        if row_vector.crs().authid() != self._bound_box.crs().authid():
            transform_context = QgsProject.instance().transformContext()
            coord_transformer = QgsCoordinateTransform(row_vector.crs(), self._bound_box.crs(), transform_context)
            row_vector_geom.transform(coord_transformer)

        assert self.raster.crs().authid() == self._bound_box.crs().authid(), "Raster layer must have same CRS " \
                                                                        "as bounds vectory layer."
        self.raster.dataProvider()

        row_vector = row_vector_geom.asMultiPolyline()[0]
        start = row_vector[0]
        stop = row_vector[len(row_vector)-1]

        self._bound_box = list(self._bound_box.getFeatures())[0].geometry()

        assert self._bound_box.contains(row_vector[0])

        theta = math.atan2(stop[1] - start[1], stop[0] - start[0])

        self.row_h_geo_dx = math.cos(theta) * self.row_h
        self.row_h_geo_dy = math.sin(theta) * self.row_h
        self.col_w_geo_dx = math.cos(theta + math.pi / 2) * self.col_w
        self.col_w_geo_dy = math.sin(theta + math.pi / 2) * self.col_w
        if row_h_stdev > 0:
            self.row_h_stdev = row_h_stdev / self.row_h
        if point_interval_stdev > 0:
            self.col_w_stdev = point_interval_stdev / self.col_w

        # init self params
        self._root = PinDropperPin(0, 0, None, -1)
        self._root.drop_geolocation(*start)
        self._defined_points[self._root.coords_indexes()] = self._root
        self._loose_ends = self._root.loose_ends_dict()

        ds = gdal.Open(self.raster.dataProvider().dataSourceUri())
        self.raster_data = np.stack([
            ds.GetRasterBand(band+1).ReadAsArray()
            for band
            in range(self.raster.dataProvider().bandCount())
        ], axis=-1)

        self.band_ranges = np.stack([
            np.amin(self.raster_data, axis=tuple(range(len(self.raster_data.shape)-1))),
            np.amax(self.raster_data, axis=tuple(range(len(self.raster_data.shape)-1)))
        ], axis=-1)

        blank_axes = self.band_ranges[:,0] != self.band_ranges[:,1]
        self.raster_data = self.raster_data[:, :, blank_axes]
        self.band_ranges = self.band_ranges[blank_axes, :]
        del ds  # save memory

        approx_total_calcs = self._bound_box.area() / ((self.row_h_geo_dx + self.col_w_geo_dx) * (self.row_h_geo_dy + self.col_w_geo_dy))

        feedback.setProgress(0)
        feedback.pushInfo("Starting area search")
        print("Debug log begin")
        itercount = 0
        # for debugging, you can change this value to have the algorithm stop before it's technically done
        max_points = approx_total_calcs * 2
        # max_points = 200
        while not self.is_complete() and self.population() < max_points:
            feedback.pushInfo("Iteration %d: %d loose ends" % (itercount, len(self._loose_ends)))
            t_iter_begin = time()
            old_loose = {point: self._loose_ends[point] for point in self._loose_ends}
            self._loose_ends = {}
            pins_dropped = 0
            for loose_end in old_loose.values():
                if feedback.isCanceled():
                    break
                success = self.drop_pin(loose_end)
                feedback.pushInfo("Tried to drop pin at coords (%d, %d) - %s" %
                                  (loose_end.x_index(), loose_end.y_index(), ("success" if success else "failure")))
                pins_dropped = pins_dropped + 1
            feedback.pushInfo("Checked %d pins in %f seconds!" % (pins_dropped, time() - t_iter_begin))
            self.make_connections()

            itercount = itercount + 1

            feedback.setProgress(int(100 * self.population() / approx_total_calcs))
            feedback.setProgressText("%d / ~%d" % (self.population(), approx_total_calcs))

        # read values from source csv file
        # (for now generate random values from 1 to 5)
        values = {coords: randint(1, 5) for coords in self._defined_points}

        # set output field values
        for i in range(len(self._defined_points)):  # if you're concerned, the order here does NOT matter
            coords = list(self._defined_points.keys())[i]
            pin = self._defined_points[coords]
            feat = QgsFeature(id=i)
            # for i in range(num_attrs):
            #     feat.setAttribute(i, )
            # feat.setAttributes((*coords, values[coords]))
            feat.setGeometry(QgsPoint(*pin.geoCoords()))
            self._sink.addFeature(feat, QgsFeatureSink.FastInsert)

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUT: dest_id}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Drop Pins Semi-Regularly'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Vector creation'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PinDropperAlgorithm()

    # my functions
    def is_complete(self):
        return len(self._loose_ends) == 0

    def drop_pin(self, point_candidate):
        '''
        evaluates a point candidate and drops a pin on it if it's within the bounds of the bounding box
        '''
        parent, relation = point_candidate.parent_relation()
        # relation is from the child's POV, so if the parent is to the left of the child, it will be DIRECTION_LEFT
        relation_tup = PinDropperPin.DIRECTIONS[reverse_direction(relation)]
        approx_geo_x = parent.geoX() + relation_tup[0] * self.col_w_geo_dx + relation_tup[1] * self.row_h_geo_dx
        approx_geo_y = parent.geoY() + relation_tup[0] * self.col_w_geo_dy + relation_tup[1] * self.row_h_geo_dy

        # ignore values with approximate values outside the bounding box
        if self._bound_box.contains(QgsPointXY(approx_geo_x, approx_geo_y)):
            if self.near_border(approx_geo_x, approx_geo_y):
                point_candidate.status(PinDropperPin.STATUS_HOLE)
                return False
            else:
                # print("Sampling target %f, %f" % (parent.geoX(), parent.geoY()))
                target = self.sample(parent.geoX(), parent.geoY())
                point, rating = self.search(target, approx_geo_x, approx_geo_y)
                if rating >= self.overlay_match_min_threshold:
                    geo_x, geo_y = point
                if rating < self.overlay_match_min_threshold and self.assume_empties:
                    geo_x, geo_y = approx_geo_x, approx_geo_y
                if rating >= self.overlay_match_min_threshold or self.assume_empties:
                    point_candidate.drop_geolocation(geo_x, geo_y)
                    self._defined_points[point_candidate.coords_indexes()] = point_candidate
                    new_loose_dict = point_candidate.loose_ends_dict()
                    self._loose_ends.update(
                        {p: new_loose_dict[p]
                         for p in new_loose_dict
                         if p not in self._loose_ends}
                        )  # avoid adding multiple loose ends for the same x,y pair
                    return True
                else:
                    # flag pin as hole TODO: figure out hole handling!
                    point_candidate.status(PinDropperPin.STATUS_HOLE)
                    return False
        else:  # if the loose end is outside the bounds of the network, flag it as a dead end
            point_candidate.status(PinDropperPin.STATUS_DEAD_END)
            return False

    def near_border(self, x, y):
        '''

        '''
        pline = QgsGeometry.fromPolylineXY(self._bound_box.asPolygon()[0])
        distance = pline.shortestLine(QgsGeometry.fromPointXY(QgsPointXY(x, y))).length()
        return distance < math.sqrt(math.pow(self.row_h, 2) + math.pow(self.col_w, 2))

    def make_connections(self):
        '''
        replaces loose-end pins at the locations of existing pins with references to the existing pins
        '''
        loose_ends_temp = {point: self._loose_ends[point] for point in self._loose_ends}
        for loose_end_coords in loose_ends_temp:
            # if there exists a defined point with the same coords as the loose end
            if loose_end_coords in self:
                # merge the loose end
                self[loose_end_coords].merge_with_loose_end(loose_ends_temp[loose_end_coords])
                self._loose_ends.pop(loose_end_coords)
        self._loose_ends = loose_ends_temp  # this line is sus, so keep an eye on it

    class SearchBox:
        def __init__(self, idx_radius, geo_center, context):
            '''
            @param idx_radiuses: an x,y tuple in row, col index scalars of the x and y radii of the search box. does
            NOT have to be int values!
            @param geo_center: an x,y tuple in geocoords (using whatever CRS we're using for everything else) for the center
            of this search box.
            @return a list of x,y geo coordinates to search, with length subdiv^2
            '''
            self.radius = idx_radius
            self.geo_center = geo_center
            # row_idx_coords = index within row, so x
            w_rad = idx_radius * context.col_w_stdev
            self.row_idx_coords = np.arange(-w_rad, w_rad, 2 * w_rad / context.search_iter_size)
            # col_idx_coords = index within a column, so y
            h_rad = idx_radius * context.row_h_stdev
            self.col_idx_coords = np.arange(-h_rad, h_rad, 2 * h_rad / context.search_iter_size)
            self.x_geo_coords = geo_center[0] + self.row_idx_coords * context.col_w_geo_dx + self.col_idx_coords * context.row_h_geo_dx
            self.y_geo_coords = geo_center[1] + self.row_idx_coords * context.col_w_geo_dy + self.col_idx_coords * context.row_h_geo_dy
            self.box_coords_list = itertools.product(self.x_geo_coords, self.y_geo_coords)

        def within(self, geo_x, geo_y):
            return self.x_geo_coords[0] < geo_x < self.x_geo_coords[self.x_geo_coords.shape[0]-1] and \
                   self.y_geo_coords[0] < geo_y < self.y_geo_coords[self.y_geo_coords.shape[0]-1]

        def coords_list(self):
            return self.box_coords_list

        def subsearch(self, center, denominator, context):
            return PinDropperAlgorithm.SearchBox(self.radius / denominator, center, context)

        def __len__(self):
            return len(self.x_geo_coords) * len(self.y_geo_coords)

    def search(self, target_pattern, center_geo_x, center_geo_y):
        '''
        searches for a match of target_pattern around center_geo_x,center_geo_y
        '''
        old_search_box = None
        search_box = None
        for search_level in range(1, 4):
            if search_level > 1:
                old_search_box = search_box
            # print("searching area around %f, %f at radius of %d standard deviations" % (center_geo_x, center_geo_y, search_level))
            search_box = PinDropperAlgorithm.SearchBox(search_level, (center_geo_x, center_geo_y), self)
            point, rating = self.search_area(target_pattern, search_box, old_search_box, self.search_iter_count)
            if rating > self.overlay_match_min_threshold:
                return point, rating
        return None, 0

    def search_area(self, target, search_box, ignore_search_box=None, iters=0):
        '''
        i have no idea how to explain this
        '''
        assert iters >= 0
        best_match = 0
        best_coords = None

        for geo_x, geo_y in search_box.coords_list():
            if ignore_search_box is not None and ignore_search_box.within(geo_x, geo_y):
                continue

            compare = self.sample(geo_x, geo_y)

            match = self.rate_offset_match(target, compare)
            if match > best_match:
                best_match = match
                best_coords = (geo_x, geo_y)

        if best_coords is None or iters == 0:
            return best_coords, best_match
        else:
            return self.search_area(target, search_box.subsearch(best_coords, 2, self), ignore_search_box, iters-1)

    def rate_offset_match(self, target, compare):
        '''
        takes two matrices of raster data and compares them, rating them by similarity
        Just to be clear I am 100% making this algorithm up.
        @param target the matrix to check match with
        @param compare the matrix to check if it matches target
        @return a value from 0 to 1, where 0 is no match and 1 is 100% match
        '''
        if target.shape != compare.shape:
            return 0    # this is a bad solution but allowing the program to handle this and move on might help figure
                        # out the problem
        difference = np.abs(compare-target)
        norm_diff = np.stack([difference[:,:,n] / (self.band_ranges[n, 1] - self.band_ranges[n, 0])
                              for n
                              in range(difference.shape[2])], axis=-1)
        avg_difference = np.mean(norm_diff)
        rating = 1.0 - avg_difference
        return rating

    def sample(self, center_geo_x, center_geo_y):
        '''
        takes values of the raster at each band in a band in a box surrounding center_geo_x,center_geo_y
        '''
        w = int(2 * self.overlay_box_radius * self.col_w)
        h = int(2 * self.overlay_box_radius * self.row_h)
        x1, y1 = self.asRasterCoords(center_geo_x - self.overlay_box_radius * self.col_w,
                                     center_geo_y - self.overlay_box_radius * self.row_h)
        x2, y2 = self.asRasterCoords(center_geo_x + self.overlay_box_radius * self.col_w,
                                     center_geo_y + self.overlay_box_radius * self.row_h)
        if x2-x1 != w:
            x2 = min(x2, x1 + w)

        if y2-y1 != h:
            y2 = min(y2, y1 + h)

        return self.raster_data[x1:x2, y1:y2, :]

        # middle code. uses RasterDataProvider.block(). could not get to work because there's v. little documentation
        # sample_width = int((2 * self.overlay_box_radius + 1) * self.overlay_box_sampling) # in num samples (pixels)
        # num_bands = self.raster.dataProvider().bandCount()
        # sample_data = np.zeros((sample_width, sample_width, num_bands))
        # point1 = QgsPointXY(center_geo_x - self.overlay_box_radius * self.col_w, center_geo_y - self.overlay_box_radius * self.row_h)
        # point2 = QgsPointXY(center_geo_x + self.overlay_box_radius * self.col_w, center_geo_y + self.overlay_box_radius * self.row_h)
        # for band in range(num_bands):
        #     sample_data[:, :, band] = self.raster.dataProvider().block(band, QgsRectangle(point1, point2), sample_width, sample_width).data()
        # return sample_data

        # old code. box aligns with field rows & columns, but FAR too computationally-intensive
        # # print ("Taking samples of box centered at %f, %f with radius of %d points and %d total samples" %
        # #        (center_geo_x, center_geo_y, sample_radius, sample_width * sample_width))
        #
        # # important note: row_sample_coord and col_sample_coord are in sampling units, not row/col units.
        # # so to change them back to row/col units, you need to divide by self.overlay_box_sampling
        # for row_sample_coord in range(-sample_radius, sample_radius):
        #     for col_sample_coord in range(-sample_radius, sample_radius):
        #         # and viola! x,y coords in raster units! probably!
        #         # (multiply columns by rows and vice versa because it's row coordinate vs. column number and vice versa)
        #         sample_geo_x = center_geo_x + (row_sample_coord * self.col_w_geo_dx + col_sample_coord * self.row_h_geo_dx) / self.overlay_box_sampling
        #         sample_geo_y = center_geo_y + (row_sample_coord * self.col_w_geo_dy + col_sample_coord * self.row_h_geo_dy) / self.overlay_box_sampling
        #         # print("Sample raster bands 1 - %d at %f,%f" % (num_bands, sample_geo_x, sample_geo_y))
        #         bands = self.raster.dataProvider().identify(QgsPointXY(sample_geo_x, sample_geo_y), QgsRaster.IdentifyFormatValue).results()
        #         bands = [bands[k] for k in bands]
        #         sample_data[row_sample_coord + sample_radius, col_sample_coord + sample_radius, :] = bands
        # return sample_data

    def asRasterCoords(self, x_geo, y_geo):
        raster_bounds = self.raster.dataProvider().extent()
        x_rel = x_geo - raster_bounds.xMinimum()
        x = (x_rel / raster_bounds.width()) * self.raster_data.shape[0]
        y_rel = y_geo - raster_bounds.yMinimum()
        y = (y_rel / raster_bounds.height()) * self.raster_data.shape[1]
        return int(x), int(y)

    def population(self):
        return len(self._defined_points)

    def __contains__(self, item):
        return item in self._defined_points

    def __getitem__(self, item):
        assert isinstance(item, tuple)
        assert len(item) == 2
        assert item in self
        return self._defined_points[item]



class PinDropperPin:

    STATUS_PIN = 0
    STATUS_LOOSE_END = 1
    STATUS_DEAD_END = 2
    STATUS_HOLE = 3

    DIRECTION_LEFT = 0
    DIRECTION_UP = 1
    DIRECTION_RIGHT = 2
    DIRECTION_DOWN = 3
    NUM_DIRECTIONS = 4
    DIRECTIONS = (
        (1, 0),
        (0, 1),
        (-1, 0),
        (0, -1)
    )

    def __init__(self, x_index, y_index, parent, origin):
        # x and y are immutable
        self._x_index = x_index
        self._y_index = y_index
        self._status = PinDropperPin.STATUS_LOOSE_END
        self._geoX = None
        self._geoY = None
        self._adjs = [None for i in range(PinDropperPin.NUM_DIRECTIONS)]
        if parent is not None: # parent will be none for the root pin
            self._adjs[origin] = parent

    def drop_geolocation(self, geoX, geoY):
        self.geoX(geoX)
        self.geoY(geoY)
        self._status = PinDropperPin.STATUS_PIN

        for i in range(PinDropperPin.NUM_DIRECTIONS):
            if self._adjs[i] is None:
                self._adjs[i] = PinDropperPin(self.x_index() + PinDropperPin.DIRECTIONS[i][0],
                                              self.y_index() + PinDropperPin.DIRECTIONS[i][1],
                                              self,
                                              reverse_direction(i)
                                              )

    def parent_relation(self):
        """
        returns a tuple of the parent of this pin and its relation, assuming this pin is a loose end.
        """
        assert self._status == PinDropperPin.STATUS_LOOSE_END
        i = list(filter(lambda x: self._adjs[x] is not None, range(PinDropperPin.NUM_DIRECTIONS)))[0]
        return self._adjs[i], i

    def loose_ends(self):
        return filter(lambda x: x.status() == PinDropperPin.STATUS_LOOSE_END, self.adjs())

    def loose_ends_dict(self):
        loose_ends = self.loose_ends()
        return {x.coords_indexes(): x for x in loose_ends}

    def status(self, new_status=-1):
        """
        retrieves or assigns pin status
        """
        if new_status > -1:
            self._status = new_status
        else:
            return self._status

    def x_index(self):
        return self._x_index

    def y_index(self):
        return self._y_index

    def coords_indexes(self):
        return self._x_index, self._y_index

    def left(self):
        return self._adjs[PinDropperPin.DIRECTION_LEFT]

    def up(self):
        return self._adjs[PinDropperPin.DIRECTION_UP]

    def right(self):
        return self._adjs[PinDropperPin.DIRECTION_RIGHT]

    def down(self):
        return self._adjs[PinDropperPin.DIRECTION_DOWN]

    def adjs(self):
        return [pin for pin in self._adjs]  # copy, don't pass a reference to the list

    def geoX(self, new_x=None):
        if new_x is not None:
            self._geoX = new_x
        else:
            return self._geoX

    def geoY(self, new_y=None):
        if new_y is not None:
            self._geoY = new_y
        else:
            return self._geoY

    def geoCoords(self):
        return self.geoX(), self.geoY()

    def merge_with_loose_end(self, loose_end):
        assert self.status() == PinDropperPin.STATUS_PIN
        assert loose_end.status() == PinDropperPin.STATUS_LOOSE_END
        assert self.coords_indexes() == loose_end.coords_indexes()
        loose_end_parent, loose_end_parent_rel = loose_end.parent_relation()
        if self._adjs[loose_end_parent_rel] is None:    # i'm not sure why this is ever the case but I could either
                                                        # spend hours on figuring that out or put this if-statement here
            self._adjs[loose_end_parent_rel] = loose_end_parent

    def __str__(self):
        pass

def reverse_direction(direction):
    return int((direction + (PinDropperPin.NUM_DIRECTIONS / 2)) % PinDropperPin.NUM_DIRECTIONS)

    def within(x,y):
        return