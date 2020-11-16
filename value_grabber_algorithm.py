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

import traceback
import geopandas as gpd
from rasterio import warp
from rasterio.crs import CRS

class ValueGrabberAlgorithm(QgsProcessingAlgorithm):

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

        vector_data = gpd.read_file(points_layer.dataProvider().dataSourceUri())
        self.rasterio_image = rasterio.open(raster_file)

        self.gcs = str(vector_data.crs).upper()
        lats = list(vector_data.lat)
        lons = list(vector_data.lon)

        output_fields = QgsFields()
        output_fields.extend(points_layer.fields())

        try:
            for bandIndex, band in enumerate(self.rasterio_image.read()):
                output_fields.append(QgsField("Band_" + str(band), QVariant.Int))
                feedback.pushInfo("Working on band... %s" % bandIndex)
                vector_data["Band_" + str(bandIndex)] = self.spec_puller_by_band(band, lons, lats)
        except IndexError:
            feedback.pushInfo("Vector and Image don't overlap.")
            feedback.pushInfo(traceback.print_exc())

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.POINTS_OUTPUT,
            context,
            fields=output_fields,
            geometryType=QgsWkbTypes.Point,
            crs=points_layer.crs(),
            sinkFlags=QgsFeatureSink.RegeneratePrimaryKey)

        count = 0
        for in_feat in points_layer.features():
            feature = QgsFeature(fields=output_fields, id=count)
            for field in output_fields.names():
                feature.setAttribute(field, vector_data[field][count])
            feature.setGeometry(in_feat.geometry())
            sink.addFeature(feature)
            count = count + 1

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

    def spec_puller_by_band(self, band, lon, lat):
        ''' This function takes a matrix of coordinates and pulls the value at
        overlap with the specified band/channel.
        raster = raster opened by rasterio
        band = number of band
        lat, lon = list of coordinates
        gcs = Geographic Coordinate System of points'''

        x_coords, y_coords = warp.transform(src_crs = CRS.from_string(self.gcs), dst_crs=self.raster.crs,
                                            xs=lon, ys=lat)

        row, col = self.raster.index(x_coords, y_coords)

        return band[row, col]
