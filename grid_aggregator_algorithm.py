from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessing,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterFeatureSink,
                       QgsRectangle,
                       QgsFeatureSink,
                       QgsWkbTypes,
                       QgsFields,
                       QgsField,
                       QgsFeature,
                       QgsGeometry,
                       QgsProcessingParameterField,
                       QgsProcessingParameterEnum,
                       QgsPointXY)

import numpy as np

from math import ceil, floor
from .value_grabber_algorithm import ValueGrabberAlgorithm

class GridAggregatorAlgorithm(QgsProcessingAlgorithm):

    GRID_CELL_W_INPUT = 'GRID_CELL_W_INPUT'
    GRID_CELL_H_INPUT = 'GRID_CELL_H_INPUT'
    FIELDS_TO_USE_INPUT = 'FIELDS_TO_USE_INPUT'
    AGGREGATION_FUNCTION_INPUT = 'AGGREGATION_FUNCTION_INPUT'
    GRID_OUTPUT = 'GRID_OUTPUT'


    def initAlgorithm(self, config):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                ValueGrabberAlgorithm.POINTS_INPUT,
                self.tr("Points"),
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.GRID_CELL_W_INPUT,
                self.tr("Grid Cell Width"),
                parentParameterName=ValueGrabberAlgorithm.POINTS_INPUT,
                minValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.GRID_CELL_H_INPUT,
                self.tr("Grid Cell Height"),
                parentParameterName=ValueGrabberAlgorithm.POINTS_INPUT,
                minValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.AGGREGATION_FUNCTION_INPUT,
                self.tr("Aggregation Function"),
                options=AGGREGATION_FUNCTIONS,
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.FIELDS_TO_USE_INPUT,
                self.tr("Fields to Use"),
                parentLayerParameterName=ValueGrabberAlgorithm.POINTS_INPUT,
                allowMultiple=True,
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.GRID_OUTPUT,
                self.tr("Output Grid")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        points_layer = self.parameterAsVectorLayer(parameters, ValueGrabberAlgorithm.POINTS_INPUT, context)
        grid_w = self.parameterAsDouble(parameters, self.GRID_CELL_W_INPUT, context)
        grid_h = self.parameterAsDouble(parameters, self.GRID_CELL_H_INPUT, context)
        fields_to_use = self.parameterAsFields(parameters, self.FIELDS_TO_USE_INPUT, context)
        ag_idx = self.parameterAsEnum(parameters, self.AGGREGATION_FUNCTION_INPUT, context)
        aggregation_function = AGGREGATION_FUNCTIONS[list(AGGREGATION_FUNCTIONS.keys())[ag_idx]]

        assert grid_w > 0, "Grid width must be greater than zero."
        assert grid_h > 0, "Grid height must be greater than zero.s"

        bounds = points_layer.extent()

        output_fields = QgsFields()
        for field in points_layer.fields():
            if field.name() in fields_to_use or (len(fields_to_use) == 0 and \
                    (field.type() == QVariant.Double or field.type() == QVariant.Int)):
                assert field.type() == QVariant.Double or field.type() == QVariant.Int, \
                    "Wrong dtype %s. Only int or double field types are supported." % field.typeName()
                output_fields.append(QgsField(field.name(), QVariant.Double))

        grid_cells = {}

        for x in range(ceil(bounds.width() / grid_w)):
            for y in range(ceil(bounds.height() / grid_h)):
                grid_cells[(x, y)] = GridAggregatorAlgorithm.GridGrabberCell(
                    floor(bounds.xMinimum()) + (x * grid_w),
                    floor(bounds.yMinimum()) + (y * grid_h),
                    floor(bounds.xMinimum()) + ((x + 1) * grid_w),
                    floor(bounds.yMinimum()) + ((y + 1) * grid_h),
                    output_fields.size()
                )

        for feature in points_layer.getFeatures():
            point = feature.geometry().asPoint()
            x = int((point.x() - floor(bounds.xMinimum())) / grid_w)
            y = int((point.y() - floor(bounds.yMinimum())) / grid_h)
            grid_cells[(x, y)].add_point(point, [feature[f] for f in output_fields.names()])

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.GRID_OUTPUT,
            context,
            fields=output_fields,
            geometryType=QgsWkbTypes.Polygon,
            crs=points_layer.crs(),
            sinkFlags=QgsFeatureSink.RegeneratePrimaryKey)

        count = 0
        for cell_coords in grid_cells:
            cell = grid_cells[cell_coords]
            feature = QgsFeature(count)
            feature.setGeometry(QgsGeometry.fromRect(cell.rect))
            cell_values = aggregation_function(cell)
            assert len(cell_values) == output_fields.size()
            cell_values = [float(x) for x in cell_values]
            feature.setAttributes(cell_values)
            sink.addFeature(feature)
            count = count + 1

        return {self.GRID_OUTPUT: dest_id}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'gridaggregator'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("Grid Aggregator")

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
        return GridAggregatorAlgorithm()

    class GridGrabberCell:
        def __init__(self, xmin, ymin, xmax, ymax, attr_count):
            self.rect = QgsRectangle(xmin, ymin, xmax, ymax)
            self.attr_count = attr_count
            self.points_within = {}

        def add_point(self, point, attrs):
            self.points_within[point] = np.array(attrs)

        def point_count(self):
            return len(self.points_within)

        def attrs_as_array(self):
            return np.stack(self.points_within.values(), axis=-1) \
                if self.point_count() > 0 \
                else np.zeros(shape=(self.attr_count, 1))

        def __getitem__(self, item):
            if isinstance(item, QgsPointXY):
                return self.points_within[item]
            elif isinstance(item, int):
                return self.points_within[self.points_within.keys()[item]]


def aggregation_function_mean(cell):
    data = cell.attrs_as_array()
    return np.mean(data, axis=1)


def aggregation_function_median(cell):
    data = cell.attrs_as_array()
    return np.median(data, axis=1)


def aggregation_function_sum(cell):
    data = cell.attrs_as_array()
    return np.sum(data, axis=1)


def aggregation_function_stdev(cell):
    data = cell.attrs_as_array()
    return np.std(data, axis=1)


def aggregation_function_weighted_average(cell):
    centerpoint = QgsPointXY((cell.rect.xMinimum() + cell.rect.xMaximum()) / 2,
                             (cell.rect.yMinimum() + cell.rect.yMaximum()) / 2)
    total_pt_distance = sum([centerpoint.distance(point) for point in cell.points_within])
    data = cell.attrs_as_array()
    if data.shape[1] < 2:
        return data
    aggregates = np.zeros(data.shape[0], np.float32)
    for point in cell.points_within:
        aggregates = aggregates + (np.array(cell[point]) * ((total_pt_distance - centerpoint.distance(point)) / total_pt_distance))
    return aggregates


AGGREGATION_FUNCTIONS = {
    "Mean Average": aggregation_function_mean,
    "Median Average": aggregation_function_median,
    "Sum": aggregation_function_sum,
    "Standard Deviation": aggregation_function_stdev,
    "Weighted Average": aggregation_function_weighted_average
}