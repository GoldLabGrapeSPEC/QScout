from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessingParameterDefinition, QgsProcessingParameterFeatureSource)
from .qscout_pin_algorithm import QScoutPinAlgorithm

class PinLocatorAlgorithm(QScoutPinAlgorithm):

    POINTS_INPUT = 'POINTS_INPUT'

    def initAlgorithm(self, config):
        super().initAlgorithm(config)

        self.addParameter(QgsProcessingParameterFeatureSource(

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

        # load input data
        data, attrs = self.load_input_data(parameters, context)

        # set up fields for output layer
        out_fields = QgsFields()
        for n, dt in attrs:
            out_fields.append(QgsField(name=n, type=dt))

        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        (self.sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields=out_fields,
            geometryType=QgsWkbTypes.Point,
            crs=self.bound_box_layer.crs(),
            sinkFlags=QgsFeatureSink.RegeneratePrimaryKey)

        # read values from source csv file
        # (for now generate random values from 1 to 5)

        # set output field values
        count = 0
        already_dropped = []
        not_dropped = []
        # first loop. add points from input data
        if data is not None:
            for entry in data:
                coords = (entry[self.input_col_attr_name], entry[self.input_row_attr_name])
                if coords in self._defined_points:
                    pin = self[coords]
                    # do conversions. qgis uses gdal, which is *VERY* finicky about fata types. gotta make sure
                    # data types are Python types, not numpy types.
                    vals = [DTYPE_CONVERSIONS[data.dtype[i].kind][1](entry[i]) for i in range(len(data.dtype))]
                    # add pin
                    count = self.add_pin_to_output(pin, vals, count)
                    # flag as dropped
                    already_dropped.append(coords)
                else:
                    # flag point as not in dropped points
                    not_dropped.append(coords)

        # second loop. add points not in input data
        if self.drop_dataless_points or data is None:
            for coords in self._defined_points:
                if coords not in already_dropped:  # don't re-add points from last loop
                    entry = [np.nan for _ in attrs]
                    # set col and row values
                    entry[self.col_attr_idx] = int(coords[0])
                    entry[self.row_attr_idx] = int(coords[1])
                    count = self.add_pin_to_output(self[coords], entry, count)

        for d in not_dropped:  # output non-dropped data in input data
            feedback.pushInfo("Did not drop coordinates for %d, %d." % d)

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUT: dest_id}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Locate Pins in Field'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'QScout'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return PinLocatorAlgorithm()
