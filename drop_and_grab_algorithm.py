from qgis.core import QgsProcessingAlgorithm
from .grid_aggregator_algorithm import *
from .qscout_pin_algorithm import QScoutPinAlgorithm

class DropAndGrabAlgoithm(QScoutPinAlgorithm):
    def initAlgorithm(self, config):
        super().initAlgorithm(config)

    def processAlgorithm(self, parameters, context, feedback):
        pass

    def name(self):
        return "dropandgrab"

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("Drop Pins and Grid Grab")

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