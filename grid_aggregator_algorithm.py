from os import sep
from importlib.util import spec_from_file_location, module_from_spec
from abc import ABC, abstractmethod
from collections.abc import Iterable
from PyQt5.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessingParameterFeatureSource,
                       QgsProcessing,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFeatureSink,
                       QgsRectangle,
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
                       QgsProject,
                       QgsProcessingParameterFileDestination)

import pandas as pd
import numpy as np

from math import ceil, floor
from .value_grabber_algorithm import QScoutValueGrabberAlgorithm
from .qscout_feature_io_algorithm import QScoutFeatureIOAlgorithm

ALLOWED_TYPES = [QVariant.Int, QVariant.Double, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong]

FIELD_CONVERTS = {
    QVariant.Double: float,
    QVariant.Int: int,
    QVariant.String: str,
    QVariant.LongLong: int,
    QVariant.ULongLong: int,
    QVariant.UInt: int
}


class QScoutGridAggregatorAlgorithm(QScoutFeatureIOAlgorithm):
    GRID_CELL_W_INPUT = 'GRID_CELL_W_INPUT'
    GRID_CELL_H_INPUT = 'GRID_CELL_H_INPUT'
    FIELDS_TO_USE_INPUT = 'FIELDS_TO_USE_INPUT'
    AGGREGATION_FUNCTION_INPUT = 'AGGREGATION_FUNCTION_INPUT'
    CUSTOM_AGGREGATION_FUNCTION_INPUT = 'CUSTOM_AGGREGATION_FUNCTION_INPUT'
    GRID_EXTENT_INPUT = 'GRID_EXTENT_INPUT'
    AGGREGATE_GRID_OUTPUT = 'GRID_OUTPUT'
    FILE_OUTPUT = 'FILE_OUTPUT'

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
                allowMultiple=True
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.AGGREGATE_GRID_OUTPUT,
                self.tr("Aggregate Grid")
            )
        )

        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.FILE_OUTPUT,
                self.tr("File Output"),
                optional=True,
                fileFilter="Excel Files (*.xlsx)"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """

        """
        self.points_input_layer = self.parameterAsVectorLayer(parameters, QScoutValueGrabberAlgorithm.POINTS_INPUT, context)
        grid_w = self.parameterAsDouble(parameters, self.GRID_CELL_W_INPUT, context)
        grid_h = self.parameterAsDouble(parameters, self.GRID_CELL_H_INPUT, context)
        fields_to_use = self.parameterAsFields(parameters, self.FIELDS_TO_USE_INPUT, context)
        ag_idx = self.parameterAsEnum(parameters, self.AGGREGATION_FUNCTION_INPUT, context)
        bounds = self.parameterAsExtent(parameters, self.GRID_EXTENT_INPUT, context)
        file_out = self.parameterAsFileOutput(parameters, self.FILE_OUTPUT, context)

        if bounds is None or bounds.area() == 0:
            # if the user didn't provide an extent, use the extent of the points layer
            bounds = self.points_input_layer.extent()
        else:
            # if the user provided an extent, it will be in the project CRS, which isn't nessecarily the same as the
            # points layer, so we gotta run a conversion
            bounds_crs = self.parameterAsExtentCrs(parameters, self.GRID_EXTENT_INPUT, context)
            bounds_crs_convert = QgsCoordinateTransform(bounds_crs, self.points_input_layer.crs(),
                                                        QgsProject.instance().transformContext())
            bounds = bounds_crs_convert.transformBoundingBox(bounds)
        aggregation_class = AGGREGATION_FUNCTIONS[list(AGGREGATION_FUNCTIONS.keys())[ag_idx]]
        if aggregation_class is not None:
            aggregator = aggregation_class(self)
        else:
            # load custom aggregation function
            ag_func_file = self.parameterAsFile(parameters, self.CUSTOM_AGGREGATION_FUNCTION_INPUT, context)
            spec = spec_from_file_location(ag_func_file[ag_func_file.find(sep):ag_func_file.find(".")],
                                           ag_func_file)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            aggregator = module.Aggregator(self)

        assert grid_w > 0, "Grid width must be greater than zero."
        assert grid_h > 0, "Grid height must be greater than zero.s"

        input_fields = []
        self.output_fields = QgsFields()
        if aggregator.manual_field_ag():
            for field_name, field_dtype in aggregator.return_vals():
                self.feature_output_fields().add(field_name, field_dtype)
            input_fields = [f.name() for f in self.points_input_layer.fields()]
        for field in self.points_input_layer.fields():
            if field.name() in fields_to_use:
                assert field.type() in ALLOWED_TYPES or aggregation_class is None, \
                    "Wrong dtype %s. Only int or double field types are supported." % field.typeName()
                # allow aggregators for non-numeric data types if using a custom aggregation class
                for return_val_name, return_val_dtype in aggregator.return_vals():
                    return_val_dtype = field.type() if return_val_dtype is None else return_val_dtype
                    self.feature_output_fields().append(QgsField(return_val_name + field.name(), return_val_dtype))
                input_fields.append(field.name())

        assert len(input_fields) == self.output_fields.size()

        grid_cells = self.setup_grid(bounds, grid_w, grid_h)

        xstart = floor(bounds.xMinimum())
        ystart = floor(bounds.yMinimum())
        df_w = ceil(bounds.width() / grid_w) + 1
        df_h = ceil(bounds.height() / grid_h) + 1
        fprogress = 0
        ftotal = self.points_input_layer.featureCount() + (df_w * df_h)

        for feature in self.feature_input():
            if feedback.isCanceled():
                return {self.AGGREGATE_GRID_OUTPUT: None, self.FILE_OUTPUT: None}
            if feature.hasGeometry() and feature.geometry() is not None:
                point = feature.geometry().asPoint()
                x = int((point.x() - xstart) / grid_w)
                y = int((point.y() - ystart) / grid_h)
                if (x, y) in grid_cells:
                    vals_dict = {f: (feature[f].value() if not QVariant.isNull(feature[f]) else np.NAN) if isinstance(feature[f], QVariant)
                                                       else feature[f] for f in input_fields}
                    grid_cells[(x, y)].add_point(point, vals_dict)
                else:
                    feedback.pushInfo("(%s, %s) outside bounds." % (point.x(), point.y()))
            else:
                feedback.pushInfo("Feature %s has no geometry. Skipping." % feature.id())
            fprogress += 1
            feedback.setProgress(100 * int(fprogress / ftotal))

        dest_id = self.create_sink(
            parameters,
            self.AGGREGATE_GRID_OUTPUT,
            context,
            QgsWkbTypes.Polygon
        )

        count = 0

        grid_arrs = [np.full(shape=(df_h, df_w), fill_value=np.nan, dtype=np.dtype(FIELD_CONVERTS[f.type()])) for f in self.output_fields]
        grid_arrs.append(np.full(shape=(df_h, df_w), dtype=np.int_, fill_value=0))

        for x, y in grid_cells:
            if feedback.isCanceled():
                return {self.AGGREGATE_GRID_OUTPUT: None, self.FILE_OUTPUT:None}
            cell_coords = (x, y)
            cell = grid_cells[cell_coords]
            feature = QgsFeature(count)
            feature.setGeometry(QgsGeometry.fromRect(cell.rect))
            cell_values = aggregator.aggregate(cell)
            for i, v in enumerate(cell_values):
                grid_arrs[i][y, x] = v
            grid_arrs[len(cell_values)][y, x] = cell.point_count()
            assert len(cell_values) == self.feature_output_fields().size()
            feature.setAttributes(cell_values)
            count = self.append_to_feature_output(feature, count)

            fprogress += 1
            feedback.setProgress(100 * int(fprogress / ftotal))

        grid_arrs = [np.flipud(a) for a in grid_arrs]

        if file_out:
            try:
                with pd.ExcelWriter(file_out, engine="openpyxl") as fout:
                    for i, field in enumerate(self.output_fields):
                        df = pd.DataFrame(grid_arrs[i])
                        df.to_excel(fout, sheet_name=field.name(), header=False, index=False)
                    df = pd.DataFrame(grid_arrs[len(self.output_fields)])
                    df.to_excel(fout, sheet_name="Point Count", header=False, index=False)
            except FileNotFoundError as e:
                fout = None
        else:
            fout = None
            feedback.pushWarning("File path '%s' invalid." % file_out)
        return {self.AGGREGATE_GRID_OUTPUT: dest_id, self.FILE_OUTPUT: fout}

    def setup_grid(self, bounds, grid_w, grid_h):
        grid_cells = {}

        xstart = floor(bounds.xMinimum())
        ystart = floor(bounds.yMinimum())

        for x in range(ceil(bounds.width() / grid_w) + 1):
            for y in range(ceil(bounds.height() / grid_h) + 1):
                grid_cells[(x, y)] = QScoutGridAggregatorAlgorithm.GridAggregatorCell(
                    xstart + (x * grid_w),
                    ystart + (y * grid_h),
                    xstart + ((x + 1) * grid_w),
                    ystart + ((y + 1) * grid_h),
                    self.feature_output_fields().size()
                )
        return grid_cells

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
        return QScoutGridAggregatorAlgorithm()

    def feature_input(self):
        """
        should return an iterable, generally either a QgsFeatureIterator or list
        """
        return self.points_input_layer.getFeatures()

    def feature_input_crs(self):
        return self.points_input_layer.crs()

    def feature_output_fields(self):
        return self.output_fields

    class GridAggregatorCell:
        def __init__(self, xmin, ymin, xmax, ymax, attr_count):
            self.rect = QgsRectangle(xmin, ymin, xmax, ymax)
            self._attr_count = attr_count
            self._points_within = {}

        def add_point(self, point, attrs):
            assert len(attrs) == self.attr_count()
            self._points_within[point] = attrs

        def point_count(self):
            return len(self._points_within)

        def attr_count(self):
            return self._attr_count

        def points_data(self):
            return list(self._points_within.values())

        def points_within(self):
            return list(self._points_within.keys())

        def point_within(self, i):
            return self.points_within()[i]

        def attrs_as_array(self, fields=None):
            """
            returns the attributes of the points within this cell as a numpy array
            if passed a list of fields, returns list of numpy arrays with each array corresponding to a field
            """
            if fields is None:
                if self.point_count() == 0:
                    return np.zeros(shape=(self.attr_count(), 1))
                arr = np.stack([list(p.values()) for p in self.points_data()], axis=-1)
                return arr #if len(arr.shape) == 1 else arr[:, np.newaxis]
            if not isinstance(fields, Iterable):
                fields = [fields]
            # it's assumed that if you're using this function with specific fields, you're probably using a custom
            # aggregation function, which you can competantly troubleshoot on your own
            return [np.array([p[f] for p in self.points_data()]) for f in fields]

        def __getitem__(self, item, fields=None):
            if isinstance(item, QgsPointXY):
                point_vals = self._points_within[item]
            elif isinstance(item, int):
                point_vals = self._points_within[self._points_within.keys()[item]]
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

    def manual_field_ag(self):
        return False


class QScoutAggregationFunctionMean(QScoutAggregationFunction):
    def return_vals(self):
        return [("Mean_", QVariant.Double)]

    def aggregate(self, cell):
        data = np.nanmean(cell.attrs_as_array(), axis=1)
        return [float(d) for d in data]


class QScoutAggregationFunctionMedian(QScoutAggregationFunction):
    def return_vals(self):
        return [("Median_", QVariant.Double)]

    def aggregate(self, cell):
        data = np.nanmedian(cell.attrs_as_array(), axis=1)
        return [float(d) for d in data]


class QScoutAggregationFunctionSum(QScoutAggregationFunction):
    def return_vals(self):
        return [("Total", None)]

    def aggregate(self, cell):
        data = np.nansum(cell.attrs_as_array(), axis=1)
        return [float(d) for d in data]


class QScoutAggregationFunctionStdev(QScoutAggregationFunction):
    def return_vals(self):
        return [("Stdev_", QVariant.Double)]

    def aggregate(self, cell):
        data = np.nanstd(cell.attrs_as_array(), axis=1)
        return [float(d) for d in data]

class QScoutAggregationFunctionMinMax(QScoutAggregationFunction):
    def return_vals(self):
        return [("Min_", QVariant.Double), ("Max_", QVariant.Double)]

    def aggregate(self, cell):
        data = cell.attrs_as_array()
        minmax = np.stack([np.amin(data,axis=1), np.aamax(data, axis=1)], axis=0).flatten('F')
        return [float(d) for d in minmax]

class QScoutAggregationFunctionWeightedAverage(QScoutAggregationFunction):
    def return_vals(self):
        return [("Average_", QVariant.Double)]

    def aggregate(self, cell):
        centerpoint = QgsPointXY((cell.rect.xMinimum() + cell.rect.xMaximum()) / 2,
                                 (cell.rect.yMinimum() + cell.rect.yMaximum()) / 2)
        total_pt_distance = sum([centerpoint.distance(point) for point in cell.points_within()])
        data = cell.attrs_as_array()
        if data.shape[1] < 2:
            return data
        aggregates = np.zeros(data.shape[0], np.float32)
        for point in cell.points_within():
            aggregates = aggregates + (
                        np.array(cell[point]) * ((total_pt_distance - centerpoint.distance(point)) / total_pt_distance))
        return [float(d) for d in aggregates]


AGGREGATION_FUNCTIONS = {
    "Mean Average": QScoutAggregationFunctionMean,
    "Median Average": QScoutAggregationFunctionMedian,
    "Sum": QScoutAggregationFunctionSum,
    "Standard Deviation": QScoutAggregationFunctionStdev,
    "Weighted Average": QScoutAggregationFunctionWeightedAverage,
    "Custom": None
}
