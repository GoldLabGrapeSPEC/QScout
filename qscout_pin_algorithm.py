import itertools
import math
import re
from osgeo import gdal
from time import time

from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessing,
                       QgsProject,
                       QgsCoordinateTransform,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterBoolean,
                       QgsPointXY,
                       QgsGeometry)

from .qscout_utils import *

from . import match_functions # import package, not specifics

ROW_NAME = 'row'
COL_NAME = 'col'



MATCH_FUNCTIONS = {"Regular": None, **match_functions.MATCH_FUNCTIONS}

START_CORNERS = [
    "Bottom Left",
    "Bottom Right",
    "Top Left",
    "Top Right"
]

class QScoutPinAlgorithm(QgsProcessingAlgorithm):
    # PARAMETERS

    # basics
    TARGETING_RASTER_INPUT = 'RASTER_INPUT'
    BOUND_BOX_INPUT = 'BOUND_BOX_INPUT'
    PATCH_SIZE_INPUT = 'PATCH_SIZE_INPUT'
    START_CORNER_INPUT = 'START_CORNER_INPUT'

    # row and point interval
    ROW_VECTOR_INPUT = 'R0W_VECTOR_INPUT'
    ROW_SPACING_INPUT = 'ROW_SPACING_INPUT'
    ROW_SPACING_STDEV_INPUT = 'ROW_SPACING_STDEV_INPUT'
    POINT_INTERVAL_INPUT = 'POINT_INTERVAL_INPUT'
    POINT_INTERVAL_STDEV_INPUT = 'POINT_INTERVAL_STDEV_INPUT'

    # overlay for comparisons between plants
    OVERLAY_BOX_RADIUS_INPUT = 'OVERLAY_BOX_RADIUS_INPUT'
    OVERLAY_MATCH_THRESHOLD_INPUT = 'OVERLAY_MATCH_THRESHOLD_INPUT'

    # parameters for searching for overlay matches
    SEARCH_NUM_ITERATIONS_INPUT = 'SEARCH_NUM_ITERATIONS_INPUT'
    SEARCH_ITERATION_SIZE_INPUT = 'SEARCH_ITERATION_SIZE_INPUT'
    # output field name

    # testing parameters
    RATE_OFFSET_MATCH_FUNCTION_INPUT = 'RATE_OFFSET_MATCH_FUNCTION_INPUT'
    PRECISION_BIAS_COEFFICIENT_INPUT = 'PRECISION_BIAS_COEFFICIENT_INPUT'
    COMPARE_FROM_ROOT_INPUT = 'COMPARE_FROM_ROOT'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # raster layer. repeating pattern in the raster will be used to drop pins
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.TARGETING_RASTER_INPUT,
                self.tr('Raster Layer'),
                [QgsProcessing.TypeRaster],
                optional=True
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

        # direction vector for rows
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.ROW_VECTOR_INPUT,
                self.tr('Row Vector'),
                [QgsProcessing.TypeVectorLine],
            )
        )

        # rating function
        param = QgsProcessingParameterEnum(
            self.RATE_OFFSET_MATCH_FUNCTION_INPUT,
            self.tr("Rate Offset Match Function"),
            options=MATCH_FUNCTIONS,
            defaultValue=0  # nothing I write here makes any difference
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        # whether to compare from root
        param = QgsProcessingParameterBoolean(
            self.COMPARE_FROM_ROOT_INPUT,
            self.tr("Compare from Root"),
            defaultValue=False
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        # row height
        self.addParameter(
            QgsProcessingParameterDistance(
                self.ROW_SPACING_INPUT,
                self.tr('Row Spacing'),
                parentParameterName=self.BOUND_BOX_INPUT,
                minValue=0
            )
        )

        # point interval
        self.addParameter(
            QgsProcessingParameterDistance(
                self.POINT_INTERVAL_INPUT,
                self.tr('Point Interval'),
                parentParameterName=self.BOUND_BOX_INPUT,
                minValue=0
            )
        )

        # overlay box radius
        param = QgsProcessingParameterNumber(
            self.OVERLAY_BOX_RADIUS_INPUT,
            self.tr('Overlay Box Radius'),
            type=QgsProcessingParameterNumber.Integer,
            minValue=0,
            defaultValue=2
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        # match threshold
        self.addParameter(
            QgsProcessingParameterNumber(
                self.OVERLAY_MATCH_THRESHOLD_INPUT,
                self.tr("Match Threshold"),
                type=QgsProcessingParameterNumber.Double,
                minValue=0,
                maxValue=1,
                defaultValue=.85,  # this number has absolutely no scientific or mathematical basis
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.START_CORNER_INPUT,
                self.tr("Start Corner"),
                options=START_CORNERS,
                defaultValue=0
            )
        )

        # patch size
        param = QgsProcessingParameterNumber(
            self.PATCH_SIZE_INPUT,
            self.tr('Maximum Patch Size'),
            type=QgsProcessingParameterNumber.Integer,
            minValue=0,
            defaultValue=2
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        # optional parameters
        param = QgsProcessingParameterNumber(
            self.ROW_SPACING_STDEV_INPUT,
            self.tr('Row Spacing Stdev'),
            type=QgsProcessingParameterNumber.Double,
            minValue=0,
            optional=True
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        # patch size
        param = QgsProcessingParameterNumber(
            self.POINT_INTERVAL_STDEV_INPUT,
            self.tr('Point Interval Stdev'),
            type=QgsProcessingParameterNumber.Double,
            minValue=0,
            optional=True
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        # search iteration size
        param = QgsProcessingParameterNumber(
            self.SEARCH_ITERATION_SIZE_INPUT,
            self.tr("Search Iteration Size"),
            type=QgsProcessingParameterNumber.Integer,
            minValue=2,
            defaultValue=5
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        # number of search iterations
        param = QgsProcessingParameterNumber(
            self.SEARCH_NUM_ITERATIONS_INPUT,
            self.tr("Number of Search Iterations"),
            type=QgsProcessingParameterNumber.Integer,
            minValue=1,
            defaultValue=2
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        # precision bias coefficient
        param = QgsProcessingParameterNumber(
            self.PRECISION_BIAS_COEFFICIENT_INPUT,
            self.tr("Precision Bias Coefficient"),
            type=QgsProcessingParameterNumber.Double,
            minValue=0,
            defaultValue=0

        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

    def load_params(self, parameters, context):
        # required parameters
        self.raster = self.parameterAsRasterLayer(parameters, self.TARGETING_RASTER_INPUT, context)
        self.bound_box_layer = self.parameterAsVectorLayer(parameters, self.BOUND_BOX_INPUT, context)
        self.overlay_box_radius = self.parameterAsDouble(parameters, self.OVERLAY_BOX_RADIUS_INPUT, context)
        self.col_w = self.parameterAsDouble(parameters, self.POINT_INTERVAL_INPUT, context)
        assert self.col_w > 0, "Point interval must be greater than zero."
        self.row_h = self.parameterAsDouble(parameters, self.ROW_SPACING_INPUT, context)
        assert self.row_h > 0, "Row spacing must be greater than zero."
        self.row_vector_layer = self.parameterAsVectorLayer(parameters, self.ROW_VECTOR_INPUT, context)
        # self.ignore_raster = self.parameterAsBoolean(parameters, self.IGNORE_RASTER_INPUT, context)

        # optional parameters
        row_h_stdev = self.parameterAsDouble(parameters, self.ROW_SPACING_STDEV_INPUT, context)
        point_interval_stdev = self.parameterAsDouble(parameters, self.POINT_INTERVAL_STDEV_INPUT, context)
        self.overlay_match_min_threshold = self.parameterAsDouble(parameters, self.OVERLAY_MATCH_THRESHOLD_INPUT,
                                                                  context)
        self.search_iter_count = self.parameterAsInt(parameters, self.SEARCH_NUM_ITERATIONS_INPUT, context) - 1
        self.search_iter_size = self.parameterAsInt(parameters, self.SEARCH_ITERATION_SIZE_INPUT, context)
        self.patch_size = self.parameterAsInt(parameters, self.PATCH_SIZE_INPUT, context)
        offset_func_idx = self.parameterAsEnum(parameters, self.RATE_OFFSET_MATCH_FUNCTION_INPUT, context)
        self.rate_offset_match = list(MATCH_FUNCTIONS.values())[offset_func_idx]
        self.compare_from_root = self.parameterAsBool(parameters, self.COMPARE_FROM_ROOT_INPUT, context)
        self.precision_bias_coeff = self.parameterAsDouble(parameters, self.PRECISION_BIAS_COEFFICIENT_INPUT, context)

        self.start_corner = self.parameterAsEnum(parameters, self.START_CORNER_INPUT, context)

        assert self.search_iter_size % 2 == 1, "Search iteration size should be odd to include search centerpoint."

        assert self.raster is not None or self.rate_offset_match is None, "All rate functions except 'Regular' require" \
                                                                          "a raster layer."

        self.overlay_box_radius += .5

        if row_h_stdev > 0:
            self.row_h_stdev = row_h_stdev / self.row_h
        if point_interval_stdev > 0:
            self.col_w_stdev = point_interval_stdev / self.col_w

    def load_raster_data(self):
        """
        using gdal, loads raster data from file specified in parameters.
        assigns class attributes self.raster_data, self.band_ranges, and self.raster_transform
        """
        # use gdal to open raster layer
        ds = gdal.Open(self.raster.dataProvider().dataSourceUri())
        # oddly specific error message is oddly specific for the reason you're guessing
        assert ds is not None, "Raster layer data provider URI not accessable, or something like that. You probably " \
                               "forgot to tell the program not to use the Google Maps layer again."
        # create raster data array
        self.raster_data = np.stack([
            ds.GetRasterBand(band+1).ReadAsArray()
            for band
            in range(self.raster.dataProvider().bandCount())
        ], axis=-1)

        # calculate band ranges. important for some algorithms
        self.band_ranges = np.stack([
            np.amin(self.raster_data, axis=tuple(range(len(self.raster_data.shape) - 1))),
            np.amax(self.raster_data, axis=tuple(range(len(self.raster_data.shape) - 1)))
        ], axis=-1)

        # i'm... not actually sure what's going on in this code I wrote, but it works and I'm afraid to touch it
        blank_axes = self.band_ranges[:, 0] != self.band_ranges[:, 1]
        self.raster_data = np.transpose(self.raster_data[:, :, blank_axes], axes=(1, 0, 2))
        self.band_ranges = self.band_ranges[blank_axes, :]
        # save raster transform
        self.raster_transform = ds.GetGeoTransform()
        del ds  # save memory

    def preProcessAlgorithm(self, parameters, context):
        # declare algorithm parameters, mainly just so we have them all in on place
        self._root = None
        self.bound_box = None
        self._defined_points = {}
        self._loose_ends = None
        self.row_h_geo_dx = 0
        self.row_h_geo_dy = 0
        self.col_w_geo_dx = 0
        self.col_w_geo_dy = 0
        self.col_w_stdev = .05
        self.row_h_stdev = .05
        self.overlay_box_radius = 0
        self.coords_mins = None
        self.coords_maxs = None
        # read parameters
        self.load_params(parameters, context)

        if self.rate_offset_match is not None:
            self.load_raster_data()

        # convert row vector to the same CRS as the bounding box
        row_vector_geom = list(self.row_vector_layer.getFeatures())[0].geometry()
        if self.row_vector_layer.crs().authid() != self.bound_box_layer.crs().authid():
            transform_context = QgsProject.instance().transformContext()
            coord_transformer = QgsCoordinateTransform(self.row_vector_layer.crs(), self.bound_box_layer.crs(),
                                                       transform_context)
            row_vector_geom.transform(coord_transformer)

        # process row vector
        assert self.rate_offset_match is None or self.raster.crs().authid() == self.bound_box_layer.crs().authid(), \
            "Raster layer must have same CRS as bounds vectory layer."
        row_vector = row_vector_geom.asMultiPolyline()[0]
        start = row_vector[0]
        stop = row_vector[len(row_vector) - 1]

        # init bound box
        self.bound_box = list(self.bound_box_layer.getFeatures())[0].geometry()
        if self.bound_box.isMultipart():
            self.bound_box = self.bound_box.asGeometryCollection()[0]

        assert self.bound_box.contains(row_vector[0]), "Row vector should be within the bounding box."

        theta = math.atan2(stop[1] - start[1], stop[0] - start[0])

        self.row_h_geo_dx = math.cos(theta + math.pi / 2) * self.row_h
        self.row_h_geo_dy = math.sin(theta + math.pi / 2) * self.row_h
        self.col_w_geo_dx = math.cos(theta) * self.col_w
        self.col_w_geo_dy = math.sin(theta) * self.col_w

        # check that the row vector is within bound box
        assert not self.near_border((0, 0), *start), "Row vector should be within the bounding box."

        # establish root for pin map
        self._root = QScoutPin(0, 0, None, -1)
        self._loose_ends = {}
        self.drop_pin_at(self._root, *start)
        if self.rate_offset_match is not None:
            # sample start location
            self._root_sample = QScoutPinAlgorithm.Sample(*self._root.geoCoords(), self)
            assert self._root_sample.a is not None, "Entire root sample outside bounds despite not being near edge." \
                                                    "I have no idea how that can even happen."
            # test self-similarity. allow some leeway for rounding errors
            # not sure under what circumstances it would fail
            self_similarity = self.rate_offset_match(self, self._root_sample, self._root_sample)
            assert self_similarity > .975, "Self-similarity score: %s" % self_similarity

    def locatePoints(self, feedback):
        # Compute the number of steps to display within the progress bar
        approx_total_calcs = self.bound_box.area() / (
                    (self.row_h_geo_dx + self.col_w_geo_dx) * (self.row_h_geo_dy + self.col_w_geo_dy))

        # begin execution
        feedback.setProgress(0)
        feedback.pushInfo("Starting area search")

        itercount = 0
        # for debugging, you can change this value to have the algorithm stop before it's technically done
        max_points = approx_total_calcs * 2
        # max_points = 1
        while not self.is_complete() and self.population() < max_points:
            feedback.pushInfo("Iteration %d: %d loose ends" % (itercount, len(self._loose_ends)))
            self.id_points_iterate(feedback)
            itercount = itercount + 1

            # update progress
            feedback.setProgress(int(100 * self.population() / approx_total_calcs))
            feedback.setProgressText("%d / ~%d" % (self.population(), approx_total_calcs))

        # if the user has cancelled the process, stop everything else
        if feedback.isCanceled():
            return {self.OUTPUT: None}

        # patch holes
        if self.is_do_patches():
            holecount = self.patch_holes()
            if holecount > 0:
                feedback.pushInfo("Patched %n holes.")

    def id_points_iterate(self, feedback):
        """
        TERRIBLE method name. TODO: change
        performs an iteration of the point dropping algorithm. drops point, identifies neighbors for next iteration
        """
        t_iter_begin = time()  # clock start time
        # copy and empty loose ends so we can seperate loose ends from last iteration from those from current iteration
        old_loose = {point: self._loose_ends[point] for point in self._loose_ends}
        self._loose_ends = {}

        # init counter for dropped pins
        pins_dropped = 0

        # loop loose ends
        for loose_end in old_loose.values():
            if feedback.isCanceled(): # stop if user tells you to
                break
            # drop pin
            success = self.drop_pin(loose_end)
            # TODO: do something with return value? idk
            pins_dropped = pins_dropped + 1
        # update user
        feedback.pushInfo("Checked %d pins in %f seconds!" % (pins_dropped, time() - t_iter_begin))

        # find "loose ends" that are actually defined points and merge them out
        # i have no idea to what degree this does anything at all. TODO: check
        loose_end_coords = list(self._loose_ends.keys())
        for coords in loose_end_coords:
            # if there exists a defined point with the same coords as the loose end
            if coords in self:
                # merge the loose end
                self[coords].merge_with_loose_end(self._loose_ends[coords])
                self._loose_ends.pop(coords)

        self.refresh_mins_maxs() # ???

    def patch_holes(self):
        """
        finds "holes" and patches them

        """
        all_dropped_coords = self.points_as_array()

        holecount = 0
        # loop through the rows
        for ridx in range(self.coords_mins[1], self.coords_maxs[1]):
            row = all_dropped_coords[:, all_dropped_coords[1, :] == ridx]
            # calculate min and max indexes in row
            r_min = np.amin(row[0, :])
            r_max = np.amax(row[0, :])
            row_w = r_max - r_min
            # if the number of points dropped in this row isn't equal to the distance between the first and last point
            # that means there is at least one hole
            if row_w != row.size:
                # loop through points in row
                for x in range(r_min, r_max):
                    coords = (x, ridx)
                    # if this point is a hole
                    if coords not in self:
                        # throw to other method or we will indent forever
                        patch_success = self.patch_hole(coords)
                        holecount = holecount + 1 if patch_success else holecount

        return holecount

    def patch_hole(self, coords):
        """
        patches a hole by predicting location based on nearest neighbors
        this is hard to explain
        """
        coords = tuple(coords)  # will often be passed a np array
        assert coords not in self._defined_points

        # delegate to another function
        borders = self.identify_nearest_bordering_points(coords)

        # check that point has borders
        assert not all([b is None for b in borders]), "No borders found for point at %s" % (coords)

        # check if coords are on same row/column
        assert (borders[DIRECTION_RIGHT] is None or borders[DIRECTION_LEFT] is None) or borders[DIRECTION_RIGHT][1] == borders[DIRECTION_LEFT][1]
        assert (borders[DIRECTION_UP] is None or borders[DIRECTION_DOWN] is None) or borders[DIRECTION_UP][0] == borders[DIRECTION_DOWN][0]

        # init vars we're going to need later. there are many
        prospec_coords_x, prospec_coords_y, pin_point, hole_w, hole_h = None, None, None, None, None

        # if spacing is horozontal
        if borders[DIRECTION_RIGHT] is not None and borders[DIRECTION_LEFT] is not None:
            # calculate geographic distance between left and right borders
            geo_distance = self.geo_coords_distance(borders[DIRECTION_LEFT], borders[DIRECTION_RIGHT])
            # calculate geographic distance between hole and right border
            hole_w = self.idx_distance(borders[DIRECTION_RIGHT], coords, single_value=True)
            # distance to hole / total distance between left and right points
            rel_from_start = hole_w / self.idx_distance(borders[DIRECTION_RIGHT], borders[DIRECTION_LEFT],
                                                        single_value=True)
            # save prospective coords
            prospec_coords_x = self[borders[DIRECTION_RIGHT]].geoCoords() + geo_distance * rel_from_start

        # if spacing is vertical
        if borders[DIRECTION_UP] is not None and borders[DIRECTION_DOWN] is not None:
            # calculate geographic distance between top and bottom borders
            geo_distance = self.geo_coords_distance(borders[DIRECTION_DOWN], borders[DIRECTION_UP])
            # calculate geographic distance between hole and top border
            hole_h = self.idx_distance(borders[DIRECTION_UP], coords, single_value=True)
            # distance to hole / total distance between top and bottom points
            rel_from_start = hole_h / self.idx_distance(borders[DIRECTION_UP], borders[DIRECTION_DOWN],
                                                        single_value=True)
            # save prospective coords
            prospec_coords_y = self[borders[DIRECTION_UP]].geoCoords() + geo_distance * rel_from_start

        assert prospec_coords_x is not None or prospec_coords_y is not None

        # if the hole is larger than the maximum patch size, return False
        if ( prospec_coords_x is None or hole_w > self.patch_size) and (prospec_coords_y is None or hole_h > self.patch_size):
            return False

        # if has both horozontal and vertical borders
        if prospec_coords_x is not None and prospec_coords_y is not None:
            # weighted average of all 4 direction points
            pin_point = np.mean(np.stack([np.array(prospec_coords_x), np.array(prospec_coords_y)]), axis=0)
        elif prospec_coords_x is not None:
            # weighted average of left and right points
            pin_point = prospec_coords_x
        else:
            assert prospec_coords_y is not None
            # weighted average of top and bottom points
            pin_point = prospec_coords_y

        # should generally be false? but if not
        if coords not in self:
            self._defined_points[coords] = QScoutPin(*coords, None, None)
        # assign location to idx coord pair
        self.drop_pin_at(self[coords], *pin_point)
        # if hole was successfully patched, return true
        return True

    def identify_nearest_bordering_points(self, coords):
        """
        this method is only ever called from within patch_hole
        it calculates the nearest defined point (defined = geographic coords) in each of the 4 direction
        important to clear up: this function does NOT actually identify the nearest defined point; just the nearest
        defined point straight in any cartesian direction (cartesian direction?)
        @param coords the coords to look for nearest bordering points to
        @return an array of length NUM_DIRECTIONS (=4) containing the nearest defined point in each direction
        """

        borders = [coords, coords, coords, coords]  # start with the starting point in each of the 4 directions

        # loop the 4 directions
        for direction in range(NUM_DIRECTIONS):
            while borders[direction] not in self._defined_points:  # scary while-loop
                # keep adding the appropriate direction vector to the coord until you hit either a defined point
                # or the edge of the area we're working with
                borders[direction] = tuple(np.add(np.array(borders[direction]), np.array(DIRECTIONS[direction])))
                # if borders[direction] not in self._defined_points:
                if borders[direction][0] > self.coords_maxs[0] or \
                        borders[direction][1] > self.coords_maxs[1] or \
                        self.coords_mins[0] > borders[direction][0] or \
                        self.coords_mins[1] > borders[direction][1]:
                    borders[direction] = None # off the edge. flag.
                    break
                # the other conditon - that the point is defined, is in the while-loop conditional

        return borders

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr("QScout")

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'qscout'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def is_complete(self):
        """
        returns true if there are no loose ends, indicating that the algorithm has completed the geolocating stage
        of its process
        TODO: rename
        """
        return len(self._loose_ends) == 0

    def population(self):
        """
        returns the number of points that have been assigned geographic locations
        """
        return len(self._defined_points)

    def points_as_array(self):
        """
        returns the index coordinates of all points that have been dropped as an array
        the 0 dimension of the array is a point vector (x,y)
        the 1 dimension of the array is a list of the vectors
        """
        return np.stack(self._defined_points.keys(), axis=-1)

    def __contains__(self, item):
        """
        Returns true if the pair of coords passed is a key in the defined points dict, indicating that it has been
        assigned a geographic location, false otherwise
        The method does not check if you actually passed it a pir of x,y index coords so technically you could pass it
        something else, which would cause it to return false. I don't see the point.
        @param item for best results, a 2-length tuple of index coordinates
        @return a boolean value, true if item is a key in the dict self._defined points, false otherwise
        """
        return item in self._defined_points

    def __getitem__(self, item):
        """
        shorthand accessor for items in self._defined points
        @param item A 2-length tuple of index coords that's a key in self._defined points. If you pass it something
        that isn't a key in self._defined_points, it gets mad
        """
        assert isinstance(item, tuple)
        assert len(item) == 2
        assert item in self, "%s is not a defined point" % ([item])
        return self._defined_points[item]

    def drop_pin(self, point_candidate):
        '''
        evaluates a point candidate and drops a pin Dropon it if it's within the bounds of the bounding box
        @param point_candidate an instance of PinDropperPin with a status of STATUS_LOOSE_END
        '''
        parent, relation = point_candidate.parent_relation()
        # relation is from the child's POV, so if the parent is to the left of the child, it will be DIRECTION_LEFT
        relation_tup = DIRECTIONS[reverse_direction(relation)]
        # approximate geograptic coordinates. will use these to hone in on actual coordinates
        approx_geo_dx = relation_tup[0] * self.col_w_geo_dx + relation_tup[1] * self.row_h_geo_dx
        approx_geo_dy = relation_tup[0] * self.col_w_geo_dy + relation_tup[1] * self.row_h_geo_dy

        approx_geo_x = parent.geoX() + approx_geo_dx
        approx_geo_y = parent.geoY() + approx_geo_dy

        # ignore points which are predicted to fall outside the bounding box
        if self.bound_box.contains(QgsPointXY(approx_geo_x, approx_geo_y)):
            # in current version, this is the same as the preceeding if-statement but at one point in past development
            # there was a margin around the border
            if self.near_border(point_candidate.coords_indexes(), approx_geo_x, approx_geo_y):
                return False
            else:
                # if there's no rate function, geo coords are set to whatever we just predicted
                if self.rate_offset_match is None:
                    self.drop_pin_at(point_candidate, approx_geo_x, approx_geo_y)
                    return True
                else:
                    # get the sample we'll be comparing to point candidates
                    target = self._root_sample if self.compare_from_root else \
                        QScoutPinAlgorithm.Sample(parent.geoX(), parent.geoY(), self)
                    # I *REALLY* hope no one ever triggers this assertion
                    assert target.a is not None, "*panicked screaming*\n*breathes*\ncan't sample %s, %s." % \
                                                 (parent.geoX(), parent.geoY())
                    # perform search function
                    point, rating = self.search(target, approx_geo_x, approx_geo_y)
                    # if rating is good, assign coords
                    if rating >= self.overlay_match_min_threshold:
                        self.drop_pin_at(point_candidate, *point)

                        return True
                    # if rating is not good... I'm not sure what we're doing here? review.
                    # if rating < self.overlay_match_min_threshold and self.is_do_patches():
                    #     geo_x, geo_y = approx_geo_x, approx_geo_y
                    # # this line of code is actually really bad and throws into question whether patches are even working right now
                    # # gotta handle asap
                    # if rating >= self.overlay_match_min_threshold or self.is_do_patches():
                    #     self.drop_pin_at(point_candidate, geo_x, geo_y)
                    #     return True
                    else:
                        # point is hole. will handle later.
                        point_candidate.status(QScoutPin.STATUS_HOLE)
                        return False
        else:  # if the loose end is outside the bounds of the network, flag it as a dead end
            point_candidate.status(QScoutPin.STATUS_DEAD_END)
            return False

    def drop_pin_at(self, point, x, y):
        point.drop_geolocation(x, y)
        self._defined_points[point.coords_indexes()] = point
        new_loose_dict = point.loose_ends_dict()
        self._loose_ends.update(
            {p: new_loose_dict[p]
             for p in new_loose_dict
             if p not in self._loose_ends and p not in self._defined_points}
        )  # avoid adding multiple loose ends for the same x,y pair

    def is_do_patches(self):
        return self.patch_size > 0

    def near_border(self, point, x, y):
        """
        @param point the index coordinates of the point
        @param x the approximate geo x-coordinate of the point
        @param y the approximate geo y-coordinate of the point
        @return true of the point is within one point-radius of the border, false otherwise
        """
        if self.coords_mins is not None \
                and np.all(self.coords_mins <= np.array(point)) \
                and np.all(np.array(point) <= self.coords_maxs):
            return False
        pline = QgsGeometry.fromPolylineXY(self.bound_box.asPolygon()[0])
        # distance = pline.shortestLine(QgsGeometry.fromPointXY(QgsPointXY(x, y))).length()
        # return distance < math.sqrt(math.pow(self.row_h, 2) + math.pow(self.col_w, 2)) * .25
        return QgsGeometry.fromPointXY(QgsPointXY(x, y)).within(pline)

    class SearchBox:
        def __init__(self, idx_radius, geo_center, context):
            """
            @param idx_radiuses: an x,y tuple in row, col index scalars of the x and y radii of the search box. does
            NOT have to be int values!
            @param geo_center: an x,y tuple in geocoords (using whatever CRS we're using for everything else) for the center
            of this search box.
            @return a list of x,y geo coordinates to search, with length subdiv^2
            """
            self.radius = idx_radius
            self.geo_center = geo_center
            # row_idx_coords = index within row, so x
            w_rad = idx_radius * context.col_w_stdev
            self.row_idx_coords = np.arange(-w_rad, w_rad, 2 * w_rad / context.search_iter_size)
            # col_idx_coords = index within a column, so y
            h_rad = idx_radius * context.row_h_stdev
            self.col_idx_coords = np.arange(-h_rad, h_rad, 2 * h_rad / context.search_iter_size)
            self.x_geo_coords = geo_center[
                                    0] + self.row_idx_coords * context.col_w_geo_dx + self.col_idx_coords * context.row_h_geo_dx
            self.y_geo_coords = geo_center[
                                    1] + self.row_idx_coords * context.col_w_geo_dy + self.col_idx_coords * context.row_h_geo_dy
            self.box_coords_list = itertools.product(self.x_geo_coords, self.y_geo_coords)

            self.box_coords_list = filter(lambda p: context.bound_box.contains(QgsPointXY(p[0], p[1])),
                                          self.box_coords_list)

        def within(self, geo_x, geo_y):
            return self.x_geo_coords[0] < geo_x < self.x_geo_coords[self.x_geo_coords.shape[0] - 1] and \
                   self.y_geo_coords[0] < geo_y < self.y_geo_coords[self.y_geo_coords.shape[0] - 1]

        def coords_list(self):
            return self.box_coords_list

        def subsearch(self, center, denominator, context):
            return QScoutPinAlgorithm.SearchBox(self.radius / denominator, center, context)

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
            search_box = QScoutPinAlgorithm.SearchBox(search_level, (center_geo_x, center_geo_y), self)
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

            compare = QScoutPinAlgorithm.Sample(geo_x, geo_y, self)
            if compare.a is None:
                # entire sample outside raster bounds
                continue

            match = self.rate_offset_match(self, target, compare)
            if self.precision_bias_coeff != 0:
                # inverse square relationship
                match /= self.precision_bias_coeff * (math.pow(geo_x - search_box.geo_center[0], 2) + math.pow(
                    geo_y - search_box.geo_center[1], 2))
            if match > best_match:
                best_match = match
                best_coords = (geo_x, geo_y)

        if best_coords is None or iters == 0:
            return best_coords, best_match
        else:
            return self.search_area(target, search_box.subsearch(best_coords, 2, self), ignore_search_box,
                                    iters - 1)

    def relativize_coords(self):
        """
        makes the coordinate indexes start at zero in each direction. also handles the anchor point specified by
        the user
        believe it or not I have empirical evidence that this method actually works as intended
        """
        # default orientation is toward the bottom-left so anything other than that means flipping the
        # index coordinates along at least one axis
        flip_rows = self.start_corner % 2 != 0  # identify if the user wants the points flipped along x-axis
        flip_cols = self.start_corner > 1  # identify if user wants the points flipped along the y-axis
        row_mins, row_maxs, col_mins, col_maxs = self.calc_grid_dimensions()
        points = self._defined_points.values() # for looping purposes
        adjusted_points = {} # create new empty dict for adjusted points

        for pin in points:
            # assume that each row starts at zero but that row numbering starts at the lowest row
            # all rows should start at zero, so relitivize with the individual row mins and maxs
            pin.relativize(row_mins[pin.y_index() - self.coords_mins[1]],
                           row_maxs[pin.y_index() - self.coords_mins[1]],
                           flip_rows,
                           self.coords_mins[1], # row indexes are simple
                           self.coords_maxs[1], # row indexes are simple
                           flip_cols)
            adjusted_points[pin.coords_indexes()] = pin # put at correct point in dict

        self._defined_points = adjusted_points # replace dict

        self.refresh_mins_maxs()

    def calc_grid_dimensions(self):
        """
        calculates the minima and maxima of each row and column and returns them in numpy array form
        @return a 4-length tuple of arrays of the row mins, row maxs, col mins, and col maxs
        """
        all_dropped_coords = self.points_as_array()
        x_vals = [all_dropped_coords[0, all_dropped_coords[1, :] == y] for y in np.unique(all_dropped_coords[1, :])]
        y_vals = [all_dropped_coords[1, all_dropped_coords[0, :] == x] for x in np.unique(all_dropped_coords[0, :])]
        row_mins = np.array([min(xs) for xs in x_vals])
        col_mins = np.array([min(ys) for ys in y_vals])
        row_maxs = np.array([max(xs) for xs in x_vals])
        col_maxs = np.array([max(ys) for ys in y_vals])

        return row_mins, row_maxs, col_mins, col_maxs

    def refresh_mins_maxs(self):
        all_dropped_coords = self.points_as_array()
        # coords_mins and coords_maxs are each 1-D 2-length arrays of x and y
        self.coords_mins = np.amin(all_dropped_coords, 1)
        self.coords_maxs = np.amax(all_dropped_coords, 1)


    def calc_margins_clip(self, target, compare):
        clip = np.s_[:, :, :]
        # it's highly unlikely that two samples with the same shape but different margins will be compared
        if target.shape() != compare.shape():
            t_m, c_m = calc_margins(target, compare)
        else:
            t_m = c_m = np.s_[:, :, :]
        t_d = target.data(t_m)
        c_d = compare.data(c_m)
        if t_d.shape != c_d.shape:
            # if off-by-one error, just clip a bit and move on with your life
            if np.all(np.abs(np.array(t_d.shape) - np.array(c_d.shape)) <= 1):
                min_margins = np.minimum(t_d.shape, c_d.shape)
                clip = np.s_[0:min_margins[0] - 1, 0:min_margins[1] - 1, slice(None, None)]
            else:
                clip = None
        return t_m, c_m, clip

    class Sample:
        def __init__(self, center_geo_x, center_geo_y, context):
            """
            Constructor. Takes values of the raster at each band in a band in a box surrounding center_geo_x,center_geo_y.
            """

            self._center = (center_geo_x, center_geo_y)

            # "upper-left" geo coordinate, which means more toward the negative-X and positive-Y direction
            self._top_left_geo = [center_geo_x - context.overlay_box_radius * context.col_w,
                                  center_geo_y + context.overlay_box_radius * context.row_h]

            # "lower-right" geo coordinate, which means more toward the positive-X and negative-Y direction
            self._bottom_right_geo = [center_geo_x + context.overlay_box_radius * context.col_w,
                                      center_geo_y - context.overlay_box_radius * context.row_h]

            x1, y1 = context.asRasterCoords(*self._top_left_geo)
            x2, y2 = context.asRasterCoords(*self._bottom_right_geo)

            self._top_left_raster = [x1, y1]
            self._bottom_right_raster = [x2, y2]

            if self._top_left_raster[0] >= context.raster_data.shape[0] \
                    or self._top_left_raster[1] >= context.raster_data.shape[1] \
                    or self._bottom_right_raster[0] < 0 \
                    or self._bottom_right_raster[1] < 0:
                # entire sample is outside raster bounds. flag as garbage and move on
                # since I fixed a lot of sampling stuff I'm not sure if this will ever happen anymore
                self.a = None
                return

            # if part of the sample is outside the bounds of the raster, make that not the case and flag the offset
            # to allow the program to compare it to normal-shaped samples
            self.offsets = np.zeros(shape=[NUM_DIRECTIONS], dtype=np.int16)

            if self._top_left_raster[0] < 0:
                self.offsets[DIRECTION_LEFT] = -self._top_left_raster[0]
                self._top_left_raster[0] = 0

            if self._top_left_raster[1] < 0:
                self.offsets[DIRECTION_UP] = -self._top_left_raster[1]
                self._top_left_raster[1] = 0

            if self._bottom_right_raster[0] >= context.raster_data.shape[0]:
                self.offsets[DIRECTION_RIGHT] = context.raster_data.shape[0] - self._bottom_right_raster[0] - 1
                self._bottom_right_raster[0] = context.raster_data.shape[0] - 1

            if self._bottom_right_raster[1] >= context.raster_data.shape[1]:
                self.offsets[DIRECTION_DOWN] = context.raster_data.shape[1] - self._bottom_right_raster[1] - 1
                self._bottom_right_raster[1] = context.raster_data.shape[1] - 1

            # actually sample the raster
            self.a = context.raster_data[self._top_left_raster[0]:self._bottom_right_raster[0],
                     self._top_left_raster[1]:self._bottom_right_raster[1], :]

            # depending on which match rating algorithm is used, these may or may not ever be needed
            # calculate them on an as-needed basis. results are stored in order to cut down on the number of
            # calculations that need to be performed
            self._min = None
            self._max = None
            self._norm = None
            self._gradients = None

        def data(self, margins=np.s_[:, :]):
            """
            simple accessor. pass it a set of slices for the margins and it will do the thing
            """
            return self.a[margins]

        def min(self, band=None):
            """
            @return the minimum value for the provided band, or a 1-D array of band minima with length self.bands() if
            band is not specified
            """
            if self._min is None:
                self._min = np.amin(self.a, (0, 1))
            return self._min[band] if band is not None else self._min

        def max(self, band=None):
            """
            @return the maximum value for the provided band, or a 1-D array of band maxima with length self.bands() if
            band is not specified
            """
            if self._max is None:
                self._max = np.amax(self.a, (0, 1))
            return self._max[band] if band is not None else self._max

        def shape(self, margins=np.s_[:, :]):
            """
            quick accessor for sample data shape
            @return the shape of the sampe data
            """
            return self.data(margins).shape

        def bands(self):
            """
            @return the length of the 'bands' dimension, assumed to be the third dimension of the shape
            """
            return self.a.shape[2]

        def norm(self, margins=np.s_[:, :]):
            """
            "normalizes" the data by dividing it by the range of values within the sample
            @param margins the margins to clip the data by
            @return a "normalized" version of the data from this sample
            """
            if self._norm is None:
                self._norm = np.stack([self.a[:, :, n] / (self.max(n) - self.min(n))
                                       for n in range(self.bands())],
                                      axis=-1)
            return self._norm[margins]

        def gradients(self, margins=np.s_[:, :]):
            """
            applies the gradient algorithm to this sample
            """
            if self._gradients is None:
                self._gradients = gradient(self.a)
            return self._gradients[margins]

        def __str__(self):
            return "Sample of the raster matrix from %s to %s, corresponding to geo-coords %s, %s" % \
                   (self._top_left_raster, self._bottom_right_raster, self._top_left_geo, self._bottom_right_geo)

        def export(self, context):
            """
            method for debugging. saves the data, normalized data, and gradients from this sample as .tif files
            """
            driver = gdal.GetDriverByName("GTiff")
            transform = list(context.raster_transform)
            transform[0] = self._top_left_geo[0]
            transform[3] = self._top_left_geo[1]

            fn = "/home/josh/AgriTech/Gold Lab/test files/%f_%f.tif" % self._center
            outdata = driver.Create(fn, self.a.shape[1], self.a.shape[0], bands=3, eType=gdal.GDT_UInt16)
            outdata.SetGeoTransform(transform)
            outdata.SetProjection(context.raster.crs().toWkt())
            for band in range(self.bands()):
                arr = self.data()[:, :, band].astype(np.uint16)
                outdata.GetRasterBand(band + 1).WriteArray(arr)
            outdata.FlushCache()

            fn = "/home/josh/AgriTech/Gold Lab/test files/%f_%f_norm.tif" % self._center
            outdata = driver.Create(fn, self.a.shape[1], self.a.shape[0], bands=3, eType=gdal.GDT_Float32)
            outdata.SetGeoTransform(transform)
            outdata.SetProjection(context.raster.crs().toWkt())
            for band in range(self.bands()):
                outdata.GetRasterBand(band + 1).WriteArray(self.norm()[:, :, band].astype(np.float32))
            outdata.FlushCache()

            fn = "/home/josh/AgriTech/Gold Lab/test files/%f_%f_grad.tif" % self._center
            arr = np.average(self.gradients(), axis=3)
            outdata = driver.Create(fn, arr.shape[1], arr.shape[0], bands=3, eType=gdal.GDT_Float32)
            outdata.SetGeoTransform(transform)
            outdata.SetProjection(context.raster.crs().toWkt())
            for band in range(self.bands()):
                outdata.GetRasterBand(band + 1).WriteArray(arr[:, :, band].astype(np.float32))
            outdata.FlushCache()

            outdata = None
            driver = None

            print(self._top_left_geo, self._bottom_right_geo)

    def asRasterCoords(self, x_geo, y_geo):
        x = (x_geo - self.raster_transform[0]) / self.raster_transform[1]
        y = (y_geo - self.raster_transform[3]) / self.raster_transform[5]

        # raster_bounds = self.raster.dataProvider().extent()
        # x_rel = x_geo - raster_bounds.xMinimum()
        # x = (x_rel / raster_bounds.width()) * self.raster_data.shape[0]
        # y_rel = y_geo - raster_bounds.yMinimum()
        # y = (y_rel / raster_bounds.height()) * self.raster_data.shape[1]

        return int(round(x)), int(round(y))  # "int(round(...)) is redundant but the program gets mad if I don't

    def geo_coords_distance(self, c1, c2, absolute=False, single_value=False):
        if not isinstance(c1, QScoutPin):
            c1 = self[c1]
        if not isinstance(c2, QScoutPin):
            c2 = self[c2]

        distance = np.array(c1.geoCoords()) - np.array(c2.geoCoords())
        if absolute:
            distance = np.abs(distance)
        if single_value:
            distance = np.linalg.norm(distance)
        return distance

    def idx_distance(self, c1, c2, absolute=False, single_value=False):
        if isinstance(c1, QScoutPin):
            c1 = c1.coords_indexes()
        if isinstance(c2, QScoutPin):
            c2 = c2.coords_indexes()

        distance = np.array(c1) - np.array(c2)
        if absolute:
            distance = np.abs(distance)
        if single_value:
            distance = math.sqrt(math.pow(distance[0], 2) + math.pow(distance[1], 2))
        return distance


class QScoutPin:
    STATUS_PIN = 0
    STATUS_LOOSE_END = 1
    STATUS_DEAD_END = 2
    STATUS_HOLE = 3

    def __init__(self, x_index, y_index, parent, origin):
        self._x_index = x_index
        self._y_index = y_index
        self._status = QScoutPin.STATUS_LOOSE_END
        self._geoX = None
        self._geoY = None
        self._adjs = [None for i in range(NUM_DIRECTIONS)]
        if parent is not None:  # parent will be none for the root pin, or for patched holes
            self._adjs[origin] = parent

    def drop_geolocation(self, geoX, geoY):
        self.geoX(geoX)
        self.geoY(geoY)
        self.status(QScoutPin.STATUS_PIN)

        for i in range(NUM_DIRECTIONS):
            if self._adjs[i] is None:
                self._adjs[i] = QScoutPin(self.x_index() + DIRECTIONS[i][0],
                                          self.y_index() + DIRECTIONS[i][1],
                                          self,
                                          reverse_direction(i)
                                          )

    def parent_relation(self):
        """
        returns a tuple of the parent of this pin and its relation, assuming this pin is a loose end.
        """
        assert self.status() == QScoutPin.STATUS_LOOSE_END
        i = list(filter(lambda x: self._adjs[x] is not None, range(NUM_DIRECTIONS)))[0]
        return self._adjs[i], i

    def loose_ends(self):
        return filter(lambda x: x.status() == QScoutPin.STATUS_LOOSE_END, self.adjs())

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
        return self._adjs[DIRECTION_LEFT]

    def up(self):
        return self._adjs[DIRECTION_UP]

    def right(self):
        return self._adjs[DIRECTION_RIGHT]

    def down(self):
        return self._adjs[DIRECTION_DOWN]

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
        assert self.status() == QScoutPin.STATUS_PIN
        assert loose_end.status() == QScoutPin.STATUS_LOOSE_END
        assert self.coords_indexes() == loose_end.coords_indexes()

        loose_end_parent, loose_end_parent_rel = loose_end.parent_relation()
        if self._adjs[loose_end_parent_rel] is None:  # i'm not sure why this is ever the case but I could either
            # spend hours on figuring that out or put this if-statement here
            self._adjs[loose_end_parent_rel] = loose_end_parent
        else:
            print(
                "self: %s;\n loose_end_parent_rel: %d;\n self._adjs[loose_end_parent_rel]: %s;\n self.coords_indexes(): %s;\n loose_end: %s;\n"
                "loose_end_parent: %s" %
                (
                self, loose_end_parent_rel, self._adjs[loose_end_parent_rel], str(self.coords_indexes()), loose_end,
                loose_end_parent))
            assert False

    def relativize(self, xmin, xmax, flip_x, ymin, ymax, flip_y):
        if not flip_x:
            self._x_index = self._x_index - xmin + 1  # index from 1
        else:
            self._x_index = xmax - self._x_index + 1  # index from 1
        if not flip_y:
            self._y_index = self._y_index - ymin + 1  # index from 1
        else:
            self._y_index = ymax - self._y_index + 1  # index from 1

    def __str__(self):
        return "Point with status %d at indexes %d, %d and geo coords %s with adjacent statuses %s, %s, %s, %s" \
               % (self.status(), *self.coords_indexes(),
                  str(self.geoCoords() if self.geoX() is not None else "No geo coords"),
                  *[str(p.status()) if p is not None else "None" for p in self._adjs])


def match_index(l, regex):
    p = re.compile(regex)
    for i in range(len(l)):
        m = p.match(l[i])
        if m is not None:
            return l[i], i
    return None, -1


