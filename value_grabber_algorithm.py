from os import sep
from importlib.util import spec_from_file_location, module_from_spec
import numpy as np
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessing,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterDefinition,
                       QgsWkbTypes,
                       QgsFeatureSink,
                       QgsFeature,
                       QgsFields,
                       QgsField,
                       QgsProject,
                       QgsCoordinateTransform,
                       QgsRectangle,
                       QgsPointXY)

from .raster_plugin import QScoutRasterInterface
from .qscout_feature_io_algorithm import QScoutFeatureIOAlgorithm


class QScoutValueGrabberAlgorithm(QScoutFeatureIOAlgorithm, QScoutRasterInterface):
    POINTS_INPUT = 'POINTS_INPUT'
    RASTER_INPUT = 'RASTER_INPUT'
    GRAB_RADIUS_INPUT = 'GRAB_RADIUS_INPUT'
    GRAB_AREA_DISTANCE_WEIGHT_INPUT = 'GRAB_AREA_DISTANCE_WEIGHT_INPUT'
    GRAB_FUNCTION_INPUT = 'GRAB_FUNCTION_INPUT'
    POINTS_WITH_VALUES_OUTPUT = 'POINTS_OUTPUT'

    def initAlgorithm(self, config):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POINTS_INPUT,
                self.tr("Points Input"),
                [QgsProcessing.TypeVectorPoint]
            )
        )

        # have to use QgsProcessingParameterFile to account for rasters too large to load in qgis
        self.addParameter(
            QgsProcessingParameterFile(
                self.RASTER_INPUT,
                self.tr("Raster File Input")
            )
        )

        param = QgsProcessingParameterDistance(
            self.GRAB_RADIUS_INPUT,
            self.tr("Grab Radius"),
            parentParameterName=self.POINTS_INPUT,
            optional=True
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        param = QgsProcessingParameterNumber(
            self.GRAB_AREA_DISTANCE_WEIGHT_INPUT,
            self.tr("Grab Area Distance Weight"),
            type=QgsProcessingParameterNumber.Double,
            optional=True
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        param = QgsProcessingParameterFile(
            self.GRAB_FUNCTION_INPUT,
            self.tr("Grab Function"),
            optional=True
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.POINTS_WITH_VALUES_OUTPUT,
                self.tr("Points with Grabbed Values")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        self.points_input_layer = self.parameterAsVectorLayer(parameters, self.POINTS_INPUT, context)
        raster_file = self.parameterAsFile(parameters, self.RASTER_INPUT, context)
        self._grab_radius = self.parameterAsDouble(parameters, self.GRAB_RADIUS_INPUT, context)
        self._grab_distance_weight = self.parameterAsDouble(parameters, self.GRAB_AREA_DISTANCE_WEIGHT_INPUT, context)

        grab_func_file = self.parameterAsFile(parameters, self.GRAB_FUNCTION_INPUT, context)
        if grab_func_file.strip():
            spec = spec_from_file_location(grab_func_file[grab_func_file.find(sep):grab_func_file.find(".")],
                                           grab_func_file)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            self.grab_analysis_function = module.grab
        else:
            self.grab_analysis_function = None
        self.load_raster_data(raster_file)
        return self.grab_values(parameters, context, feedback)

    def grab_values(self, parameters, context, feedback):

        assert round(abs(self._raster_transform[1]), 4) == round(abs(self._raster_transform[5]), 4), \
            "Raster should have square pixels"

        self.raster_crs_transform = QgsCoordinateTransform(self.feature_input_crs(), self.raster_crs(),
                                                           QgsProject.instance().transformContext())

        self.output_fields = QgsFields()
        self.output_fields.extend(self.points_input_layer.fields())

        for i in range(self.num_raster_bands()):
            self.output_fields.append(QgsField(band_field(i), QVariant.Double))

        dest_id = self.create_sink(
            parameters,
            self.POINTS_WITH_VALUES_OUTPUT,
            context,
            QgsWkbTypes.Point
        )

        count = 0
        # loop features
        for in_feat in self.feature_input():
            count = self.process_pin(in_feat, count, feedback)

        return {self.POINTS_WITH_VALUES_OUTPUT: dest_id}

    def process_pin(self, in_feat, count, feedback):
        # skip features with no geometry
        if in_feat.hasGeometry():
            band_vals = self.query_raster(in_feat)
            if band_vals is not None:
                feature = QgsFeature(self.feature_output_fields(), count)
                for field in in_feat.fields().names():
                    feature.setAttribute(field, in_feat[field])

                for band in range(self.num_raster_bands()):
                    feature.setAttribute(band_field(band), float(band_vals[band]))
                feature.setGeometry(in_feat.geometry())
                count = self.append_to_feature_output(feature, count)
            else:
                feedback.pushInfo("Could not grab raster data for x:%s, y:%s" % (
                    (in_feat.geometry().asPoint().x(), in_feat.geometry().asPoint().y())))
        else:
            feedback.pushInfo("Feature %s has no geometry" % in_feat.id())
        return count

    def feature_input_crs(self):
        return self.points_input_layer.crs()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'valuegrab'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("Value Grabber")

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

    def createInstance(self):
        return QScoutValueGrabberAlgorithm()

    def grab_radius(self):
        return self._grab_radius

    def grab_distance_weight(self):
        return self._grab_distance_weight

    def get_pixel_radius_around(self, point):
        if isinstance(point, QgsPointXY):
            x = point.x()
            y = point.y()
        else:
            x = point[0]
            y = point[1]
        ref_ext = QgsRectangle(
            QgsPointXY(x - self.grab_radius(), y - self.grab_radius()),
            QgsPointXY(x + self.grab_radius(), y + self.grab_radius())
        )
        scale_factor = self.raster_crs_transform.scaleFactor(ref_ext)
        return int(abs(self._grab_radius * scale_factor * 2 / self._raster_transform[1]))

    def mesh_with_distances(self, r, cx=0, cy=0, filter_circle=True):
        xs, ys = np.meshgrid(np.arange(-r, r), np.arange(-r, r))
        xs, ys = np.ravel(xs), np.ravel(ys)
        distances = np.sqrt(np.power(xs, 2) + np.power(ys, 2))
        xs, ys = xs + cx, ys + cy
        if filter_circle:
            allowed = np.all([
                distances < r,
                -1 < xs, xs < self.raster_width(),
                -1 < ys, ys < self.raster_height()
            ], axis=0)
            xs = xs[allowed]
            ys = ys[allowed]
            distances = distances[allowed]
        return xs, ys, distances

    def query_raster(self, point_feature, bands=np.s_[:]):
        try:
            point = point_feature.geometry().asPoint()
            raster_x, raster_y = self.as_raster_coords(point.x(), point.y(), self.raster_crs_transform)
            if self._grab_radius == 0:
                return self.data(raster_x, raster_y, bands)

            rpixel = self.get_pixel_radius_around(point)
            xs, ys, distances = self.mesh_with_distances(rpixel, raster_x, raster_y)
            pixels = self.data(xs, ys, bands)

            if self.grab_analysis_function is None:
                if self.grab_distance_weight() != 0:
                    nanvals = np.any(np.isnan(pixels), axis=1)
                    weights = 1 / ((distances ** 2) * self.grab_distance_weight())
                    weights[distances == 0] = 1  # will appear as np.inf on the above line
                    return_data = np.average(pixels[~nanvals, :].astype(np.float_), axis=0, weights=weights[~nanvals])
                else:
                    return_data = np.nanmean(pixels, axis=0)
            else:
                center_geo_rasterunits = self.raster_crs_transform.transform(point)
                return_data = self.grab_analysis_function(coords=(xs, ys), distances=distances, bands=bands, pixels=pixels,
                                                          center_geo=(center_geo_rasterunits.x(), center_geo_rasterunits.y()),
                                                          center_raster=(raster_x, raster_y), feature=point_feature, context=self)
            return return_data
        except IndexError as e:
            print(e)
            return None

    def feature_input(self):
        return self.points_input_layer.getFeatures()

    def feature_output_fields(self):
        return self.output_fields

def band_field(i):
    return "Band_" + str(i+1)
