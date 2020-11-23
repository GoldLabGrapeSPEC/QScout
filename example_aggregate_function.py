import numpy as np
from PyQt5.QtCore import QVariant
from qgis.core import QgsPointXY

# example custom aggregator, a clone of the Weighted Average aggregator, but with a constructor included.

class Aggregator:
    def __init__(self, context):
        pass

    def return_vals(self):
        """
        list of 2-length tuples
        """
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
