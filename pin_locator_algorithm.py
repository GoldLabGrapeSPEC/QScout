__author__ = 'Joshua Evans'
__date__ = '2020-11-15'
__copyright__ = '(C) 2020 by Joshua Evans'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'


from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessingParameterFeatureSource, QgsFields, QgsField, QgsProcessing, QgsProject, QgsCoordinateTransform,
                       QgsWkbTypes, QgsFeatureSink, QgsProcessingParameterFeatureSink, QgsFeature, QgsGeometry)
from .qscout_pin_algorithm import QScoutPinAlgorithm


class PinLocatorAlgorithm(QScoutPinAlgorithm):

    POINTS_INPUT = 'POINTS_INPUT'
    POINTS_OUTPUT = 'POINTS_OUTPUT'

    COL_FIELD_NAME = 'plant'
    ROW_FIELD_NAME = 'row'
    OFFSET_FIELD_NAME = 'offset'


    def initAlgorithm(self, config):
        super().initAlgorithm(config)

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POINTS_INPUT,
                self.tr("Points to Index"),
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.POINTS_OUTPUT,
                self.tr("Indexes Points")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        self.preProcessAlgorithm(parameters, context)

        self.locatePoints(feedback)

        # 'relativize' the coordinates, so x and y both start at 1
        # this also includes orienting the coordinates according to the user's preferance
        self.relativize_coords()

        points_layer = self.parameterAsVectorLayer(parameters, self.POINTS_INPUT, context)

        # convert row vector to the same CRS as the bounding box
        need_correct_crs = False
        if points_layer.crs().authid() != self.bound_box_layer.crs().authid():
            need_correct_crs = True
            coord_transformer = QgsCoordinateTransform(points_layer.crs(), self.bound_box_layer.crs(),
                                                       QgsProject.instance().transformContext())

        points_data_provider = points_layer.dataProvider()

        new_fields = QgsFields(points_data_provider.fields())

        assert new_fields.append(QgsField(name=self.COL_FIELD_NAME, type=QVariant.Int)), \
            "Field name %s already in use." % self.COL_FIELD_NAME
        assert new_fields.append(QgsField(name=self.ROW_FIELD_NAME, type=QVariant.Int)), \
            "Field name %s already in use." % self.ROW_FIELD_NAME
        assert new_fields.append(QgsField(name=self.OFFSET_FIELD_NAME, type=QVariant.Double)), \
            "Field name %s already in use." % self.OFFSET_FIELD_NAME

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.POINTS_OUTPUT,
            context,
            fields=new_fields,
            geometryType=QgsWkbTypes.Point,
            crs=self.bound_box_layer.crs(),
            sinkFlags=QgsFeatureSink.RegeneratePrimaryKey)

        x_field = new_fields.indexOf(self.COL_FIELD_NAME)
        y_field = new_fields.indexOf(self.ROW_FIELD_NAME)
        offset_field = new_fields.indexOf(self.OFFSET_FIELD_NAME)

        count = 0
        num_feature = points_data_provider.featureCount()

        feedback.setProgress(0)

        for src_feature in points_layer.getFeatures():
            count = count + 1
            point = src_feature.geometry().asPoint()
            if need_correct_crs:
                point = coord_transformer.transform(point)
            x, y, distance = self.reverseLocatePoint(point)
            feature = QgsFeature(new_fields, id=src_feature.id())
            for f in points_data_provider.fields().names():
                feature.setAttribute(new_fields.indexOf(f), feature[f])
            feature.setAttribute(x_field, int(x))
            feature.setAttribute(y_field, int(y))
            feature.setAttribute(offset_field, float(distance))
            feature.setGeometry(QgsGeometry.fromPointXY(point))
            sink.addFeature(feature, QgsFeatureSink.FastInsert)
            feedback.setProgress(100 * count / num_feature)
            if count % int(num_feature / 10) == 0:
                feedback.setProgressText("Located %d of %d" % (count, num_feature))

        return {self.POINTS_OUTPUT: dest_id}  # no output

    def reverseLocatePoint(self, point):

        best_distance = None
        best_coords = None

        # O(N) algorithm. It might work for the scales we're dealing with but I can do better.
        for coords in self._defined_points.keys():
            distance = point.distance(*self[coords].geoCoords())
            if best_distance is None or best_distance > distance:
                best_distance = distance
                best_coords = coords

        return *best_coords, best_distance


    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'locatepinsinfield'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("Locate Pins in Field")

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
        return PinLocatorAlgorithm()
