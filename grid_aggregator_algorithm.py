from os import sep
from importlib.util import spec_from_file_location, module_from_spec
from abc import ABC, abstractmethod
from collections.abc import Iterable
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessing,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterFile,
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
                       QgsPointXY,
                       QgsProcessingParameterExtent,
                       QgsCoordinateTransform,
                       QgsCoordinateTransformContext,
                       QgsProject)

import numpy as np

from math import ceil, floor
from .value_grabber_algorithm import QScoutValueGrabberAlgorithm

FIELD_CONVERTS = {
    QVariant.Double: float,
    QVariant.Int: int,
    QVariant.String: str
}


class GridAggregatorAlgorithm(QgsProcessingAlgorithm):
    GRID_CELL_W_INPUT = 'GRID_CELL_W_INPUT'
    GRID_CELL_H_INPUT = 'GRID_CELL_H_INPUT'
    FIELDS_TO_USE_INPUT = 'FIELDS_TO_USE_INPUT'
    AGGREGATION_FUNCTION_INPUT = 'AGGREGATION_FUNCTION_INPUT'
    CUSTOM_AGGREGATION_FUNCTION_INPUT = 'CUSTOM_AGGREGATION_FUNCTION_INPUT'
    GRID_EXTENT_INPUT = 'GRID_EXTENT_INPUT'
    AGGREGATE_GRID_OUTPUT = 'GRID_OUTPUT'

    def initAlgorithm(self, config):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                QScoutValueGrabberAlgorithm.POINTS_INPUT,
                self.tr("Points"),
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.GRID_CELL_W_INPUT,
                self.tr("Grid Cell Width"),
                parentParameterName=QScoutValueGrabberAlgorithm.POINTS_INPUT,
                minValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.GRID_CELL_H_INPUT,
                self.tr("Grid Cell Height"),
                parentParameterName=QScoutValueGrabberAlgorithm.POINTS_INPUT,
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

        param = QgsProcessingParameterFile(
            self.CUSTOM_AGGREGATION_FUNCTION_INPUT,
            self.tr("Custom Aggregation Function"),
            optional=True
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        param = QgsProcessingParameterExtent(
            self.GRID_EXTENT_INPUT,
            self.tr("Grid Extent"),
            optional=True
        )
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)

        self.addParameter(
            QgsProcessingParameterField(
                self.FIELDS_TO_USE_INPUT,
                self.tr("Fields to Use"),
                parentLayerParameterName=QScoutValueGrabberAlgorithm.POINTS_INPUT,
                allowMultiple=True,
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.AGGREGATE_GRID_OUTPUT,
                self.tr("Aggregate Grid")
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """

        """
        points_layer = self.parameterAsVectorLayer(parameters, QScoutValueGrabberAlgorithm.POINTS_INPUT, context)
        grid_w = self.parameterAsDouble(parameters, self.GRID_CELL_W_INPUT, context)
        grid_h = self.parameterAsDouble(parameters, self.GRID_CELL_H_INPUT, context)
        fields_to_use = self.parameterAsFields(parameters, self.FIELDS_TO_USE_INPUT, context)
        ag_idx = self.parameterAsEnum(parameters, self.AGGREGATION_FUNCTION_INPUT, context)
        bounds = self.parameterAsExtent(parameters, self.GRID_EXTENT_INPUT, context)
        if bounds.area() == 0:
            bounds = points_layer.extent()
        else:
            bounds_crs = self.parameterAsExtentCrs(parameters, self.GRID_EXTENT_INPUT, context)
            bounds_crs_convert = QgsCoordinateTransform(bounds_crs, points_layer.crs(),
                                                        QgsProject.instance().transformContext())
            bounds = bounds_crs_convert.transformBoundingBox(bounds)
        aggregation_class = AGGREGATION_FUNCTIONS[list(AGGREGATION_FUNCTIONS.keys())[ag_idx]]
        if aggregation_class is not None:
            aggregator = aggregation_class(self)
        else:
            ag_func_file = self.parameterAsFile(parameters, self.CUSTOM_AGGREGATION_FUNCTION_INPUT, context)
            spec = spec_from_file_location(ag_func_file[ag_func_file.find(sep):ag_func_file.find(".")],
                                           ag_func_file)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            aggregator = module.Aggregator(self)

        assert grid_w > 0, "Grid width must be greater than zero."
        assert grid_h > 0, "Grid height must be greater than zero.s"

        input_fields = []
        output_fields = QgsFields()
        for field in points_layer.fields():
            if field.name() in fields_to_use:
                assert field.type() == QVariant.Double or field.type() == QVariant.Int or aggregation_class is None, \
                    "Wrong dtype %s. Only int or double field types are supported." % field.typeName()
                    # allow aggregators for non-numeric data types if using a custom aggregation class
                for return_val_name, return_val_dtype in aggregator.return_vals():
                    return_val_dtype = field.type() if return_val_dtype is None else return_val_dtype
                    output_fields.append(QgsField(return_val_name + field.name(), return_val_dtype))
                    input_fields.append(field.name())

        assert len(input_fields) == output_fields.size()
        grid_cells = {}

        xstart = floor(bounds.xMinimum())
        ystart = floor(bounds.yMinimum())

        for x in range(ceil(bounds.width() / grid_w) + 1):
            for y in range(ceil(bounds.height() / grid_h) + 1):
                grid_cells[(x, y)] = GridAggregatorAlgorithm.GridGrabberCell(
                    xstart + (x * grid_w),
                    ystart + (y * grid_h),
                    xstart + ((x + 1) * grid_w),
                    ystart + ((y + 1) * grid_h),
                    output_fields.size()
                )

        for feature in points_layer.getFeatures():
            if feature.hasGeometry() and feature.geometry() is not None:
                point = feature.geometry().asPoint()
                x = int((point.x() - xstart) / grid_w)
                y = int((point.y() - ystart) / grid_h)
                if (x, y) in grid_cells:
                    grid_cells[(x, y)].add_point(point, {f: feature[f] for f in input_fields})
                else:
                    feedback.pushInfo("(%s, %s) outside bounds." % (point.x(), point.y()))
            else:
                feedback.pushInfo("Feature %s has no geometry. Skipping." % feature.id())

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.AGGREGATE_GRID_OUTPUT,
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
            cell_values = aggregator.aggregate(cell)
            assert len(cell_values) == output_fields.size()
            cell_values = [float(x) for x in cell_values]
            feature.setAttributes(cell_values)
            sink.addFeature(feature)
            count = count + 1

        return {self.AGGREGATE_GRID_OUTPUT: dest_id}

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
            assert len(attrs) == self.attr_count
            self.points_within[point] = attrs

        def point_count(self):
            return len(self.points_within)

        def attrs_as_array(self, fields=None):
            """
            returns the attributes of the points within this cell as a numpy array
            if passed a list of fields, returns list of numpy arrays with each array corresponding to a field
            """
            if fields is None:
                if self.point_count() == 0:
                    return np.zeros(shape=(self.attr_count, 1))
                arr = np.stack([list(p.values()) for p in self.points_within.values()], axis=-1)
                return arr #if len(arr.shape) == 1 else arr[:, np.newaxis]
            if not isinstance(fields, Iterable):
                fields = [fields]
            # it's assumed that if you're using this function with specific fields, you're probably using a custom
            # aggregation function, which you can competantly troubleshoot on your own
            return [np.array([p[f] for p in self.points_within.values()]) for f in fields]

        def __getitem__(self, item, fields=None):
            if isinstance(item, QgsPointXY):
                point_vals = self.points_within[item]
            elif isinstance(item, int):
                point_vals = self.points_within[self.points_within.keys()[item]]
            else:
                return None  # throw a fit
            if fields is None:
                return list(point_vals.values())
            if isinstance(fields, list) or isinstance(fields, tuple):
                return point_vals[fields]
            if isinstance(fields, slice) or isinstance(fields, int):
                return list(point_vals.values())[fields]


class QScoutAggregationFunction(ABC):
    def __init__(self, context):
        pass

    @abstractmethod
    def return_vals(self):
        pass

    @abstractmethod
    def aggregate(self, cell):
        pass


class QScoutAggregationFunctionMean(QScoutAggregationFunction):
    def return_vals(self):
        return [("Mean_", QVariant.Double)]

    def aggregate(self, cell):
        data = cell.attrs_as_array()
        return np.mean(data, axis=1)


class QScoutAggregationFunctionMedian(QScoutAggregationFunction):
    def return_vals(self):
        return [("Median_", QVariant.Double)]

    def aggregate(self, cell):
        data = cell.attrs_as_array()
        return np.median(data, axis=1)


class QScoutAggregationFunctionSum(QScoutAggregationFunction):
    def return_vals(self):
        return [("Total", None)]

    def aggregate(self, cell):
        data = cell.attrs_as_array()
        return np.sum(data, axis=1)


class QScoutAggregationFunctionStdev(QScoutAggregationFunction):
    def return_vals(self):
        return [("Stdev_", QVariant.Double)]

    def aggregate(self, cell):
        data = cell.attrs_as_array()
        return np.std(data, axis=1)


class QScoutAggregationFunctionWeightedAverage(QScoutAggregationFunction):
    def return_vals(self):
        return [("Average_", QVariant.Double)]

    def aggregate(self, cell):
        centerpoint = QgsPointXY((cell.rect.xMinimum() + cell.rect.xMaximum()) / 2,
                                 (cell.rect.yMinimum() + cell.rect.yMaximum()) / 2)
        total_pt_distance = sum([centerpoint.distance(point) for point in cell.points_within])
        data = cell.attrs_as_array()
        if data.shape[1] < 2:
            return data
        aggregates = np.zeros(data.shape[0], np.float32)
        for point in cell.points_within:
            aggregates = aggregates + (
                        np.array(cell[point]) * ((total_pt_distance - centerpoint.distance(point)) / total_pt_distance))
        return aggregates


AGGREGATION_FUNCTIONS = {
    "Mean Average": QScoutAggregationFunctionMean,
    "Median Average": QScoutAggregationFunctionMedian,
    "Sum": QScoutAggregationFunctionSum,
    "Standard Deviation": QScoutAggregationFunctionStdev,
    "Weighted Average": QScoutAggregationFunctionWeightedAverage,
    "Custom": None
}
