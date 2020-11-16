import rasterio
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessing,
                       QgsProcessingParameterFeatureSink,
                       QgsWkbTypes,
                       QgsFeatureSink,
                       QgsFeature,
                       QgsFields,
                       QgsField)

from .raster_plugin import QScoutRasterPlugin

import traceback
import geopandas as gpd


class ValueGrabberAlgorithm(QgsProcessingAlgorithm, QScoutRasterPlugin):

    POINTS_INPUT = 'POINTS_INPUT'
    RASTER_INPUT = 'RASTER_INPUT'
    POINTS_OUTPUT = 'POINTS_OUTPUT'

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

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.POINTS_OUTPUT,
                self.tr("Points Output")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        points_layer = self.parameterAsVectorLayer(parameters, self.POINTS_INPUT, context)
        raster_file =self.parameterAsFile(parameters, self.RASTER_INPUT, context)

        # vector_data = gpd.read_file(points_layer.dataProvider().dataSourceUri())

        self.load_raster_data(raster_file)

        output_fields = QgsFields()
        output_fields.extend(points_layer.fields())

        for i in range(self.raster_data.shape[2]):
            output_fields.append(QgsField(band_field(i), QVariant.Int))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.POINTS_OUTPUT,
            context,
            fields=output_fields,
            geometryType=QgsWkbTypes.Point,
            crs=points_layer.crs(),
            sinkFlags=QgsFeatureSink.RegeneratePrimaryKey)
        #
        # try:
        #     for bandIndex, band in enumerate(self.rasterio_image.read()):
        #         output_fields.append(QgsField(band_field(i), QVariant.Int))
        #         feedback.pushInfo("Working on band... %s" % bandIndex)
        #         vector_data["Band_" + str(bandIndex)] = self.spec_puller_by_band(band, lons, lats)
        # except IndexError:
        #     feedback.pushInfo("Vector and Image don't overlap.")
        #     feedback.pushInfo(traceback.print_exc())

        count = 0
        try:
            for in_feat in points_layer.getFeatures():
                feature = QgsFeature(output_fields, count)
                for field in in_feat.fields().names():
                    feature.setAttribute(field, in_feat[field])
                for band in range(self.raster_data.shape[2]):
                    feature.setAttribute(band_field(band), self.query_raster(in_feat.geometry().asPoint(), band))
                feature.setGeometry(in_feat.geometry())
                sink.addFeature(feature)
                count = count + 1
        except IndexError:
            feedback.pushInfo("Vector and Image don't overlap.")
            feedback.pushInfo(traceback.print_exc())

        return {self.POINTS_OUTPUT: dest_id}

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
        return ValueGrabberAlgorithm()

    def query_raster(self, point, band):
        raster_x, raster_y = self.as_raster_coords(point.x(), point.y())
        return int(self.raster_data[raster_x, raster_y, band])

def band_field(i):
    return "Band_" + str(i+1)