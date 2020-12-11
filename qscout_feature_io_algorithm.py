from qgis.core import QgsFeatureSink, QgsProcessingAlgorithm
from abc import ABC, abstractmethod

class QScoutFeatureIOAlgorithm(QgsProcessingAlgorithm):
    """
    Abstract class for QScout algorithms that take an input set of features and/or output another set of features
    Does not need to output the same number of features it inputs
    Input and output sources can be changed during a chain of processing algorithms.
    self._feature_input can be a
    """

    @abstractmethod
    def feature_input(self):
        """
        should return an iterable, generally either a QgsFeatureIterator or list
        """
        pass

    def feature_input_crs(self):
        """
        should return a QgsCoordinateReferanceSystem object
        """
        pass

    def feature_input_fields(self):
        pass

    def feature_output(self):
        """
        should return an instance of either QgsFeatureSink or list
        """
        return self.output_sink

    def feature_output_fields(self):
        """
        should return an instance of QgsFields containing the fields for features produced by this instance
        """
        pass

    def append_to_feature_output(self, feat, count=0):
        if isinstance(self.feature_output(), QgsFeatureSink):
            self.feature_output().addFeature(feat, QgsFeatureSink.FastInsert)
        else:
            self.feature_output().append(feat)
        return count + 1

    def create_sink(self, parameters, param_name, context, geometry_type):
        if not hasattr(self, 'output_sink') or self.output_sink is None:
            (self.output_sink, dest_id) = self.parameterAsSink(
                parameters,
                param_name,
                context,
                fields=self.feature_output_fields(),
                geometryType=geometry_type,
                crs=self.feature_input_crs(),
                sinkFlags=QgsFeatureSink.RegeneratePrimaryKey)
            return dest_id
        else:
            return -1