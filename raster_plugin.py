import numpy as np
from osgeo import gdal

from qgis.core import QgsCoordinateReferenceSystem, QgsPointXY

__author__ = 'Joshua Evans'
__date__ = '2020-11-23'
__copyright__ = '(C) 2020 by Joshua Evans'


class QScoutRasterInterface:
    """
    A class for QScout plugins that use raster data. It is intended as an abstract class and while it can be
    instantiated directly, it probably shouldn't be. Instead, it should be extended by other classes, which will
    usually also extend QgsProcessingPlugin or some other class that extends QgsProcessingPlugin
    It's possible that QScoutRasterInterface should directly extend QgsProcessingPlugin. TODO: consider
    """
    def __init__(self):
        """
        default constructor. Doesn't really DO anything, so it's actually not a huge deal if it's not invoked
        in subclass constructors
        """
        self._raster_data = None
        self._band_ranges = None
        self._raster_crs = None
        self._raster_transform = None
        self._rot = None
        self._trans = None

    def load_raster_data(self, raster_file):
        """
        using gdal, loads raster data from the passed arguement
        assigns class attributes self.raster_data, self.band_ranges, and self.raster_transform, self.rot, self.trans,
        self.raster_crs
        @param raster_file a path to the raster file to open
        """
        # use gdal to open raster layer
        ds = gdal.Open(raster_file)
        # oddly specific error message is oddly specific for the reason you're guessing
        assert ds is not None, "Raster layer data provider URI not accessable, or something like that."
        # create raster data array
        self._raster_data = np.stack([
            ds.GetRasterBand(band+1).ReadAsArray()
            for band
            in range(ds.RasterCount)
        ], axis=-1)

        # calculate band ranges. important for some algorithms
        self._band_ranges = np.stack([
            np.amin(self._raster_data, axis=tuple(range(len(self._raster_data.shape) - 1))),
            np.amax(self._raster_data, axis=tuple(range(len(self._raster_data.shape) - 1)))
        ], axis=-1)

        # i'm... not actually sure what's going on in this code I wrote, but it works and I'm afraid to touch it
        blank_axes = self._band_ranges[:, 0] != self._band_ranges[:, 1]
        self._raster_data = np.transpose(self._raster_data[:, :, blank_axes], axes=(1, 0, 2))
        self._band_ranges = self._band_ranges[blank_axes, :]
        self._raster_crs = QgsCoordinateReferenceSystem(ds.GetProjection())
        # save raster transform
        self._raster_transform = ds.GetGeoTransform()
        self._rot = np.array(self._raster_transform)[np.array([1, 2, 4, 5])].reshape(2, 2)
        self._trans = np.array(self._raster_transform)[np.array([0, 3])].reshape(2, 1)
        del ds  # save memory

    def as_raster_coords(self, x_geo, y_geo, crs_transform=None):
        """
        takes an x,y coord pair or a set of x,y coordinate pairs in geo coordinates and returns raster coordinates
        (pixels)
        @param x_geo an x coordinate or set of x-coordinates
        @param y_geo a y coordinate or set of y-coordinates
        @param crs_transform a QgsCoordinateTransform to apply to x_geo and y_geo before the raster transform
        @return a tuple of x,y coordinates if passed single vales or a tuple of arrays of x and y coordinates if passed
        arrays. coordinates will be int values, not nessecarily within the range of the raster size
        """
        if crs_transform is not None:
            if isinstance(x_geo, np.ndarray):
                x_geo, y_geo = crs_transform.transformCoords(numPoint=x_geo.size(), x=x_geo, y=y_geo)
            else:
                point = crs_transform.transform(QgsPointXY(x_geo, y_geo))
                x_geo = point.x()
                y_geo = point.y()
        if not isinstance(x_geo, np.ndarray):
            x_geo = np.array([x_geo])
            y_geo = np.array([y_geo])
        coords = np.stack([x_geo, y_geo], axis=0)
        x, y = self.trreversetransform(coords)
        if x.shape[0] == 1:
            # "int(round(...)) is redundant but the program gets mad if I don't
            return int(round(x[0])), int(round(y[0]))
        else:
            return x.astype(np.int_), y.astype(np.int_)

    def as_geo(self, x_pixels, y_pixels):
        """
        reverses the operations of as_raster_coords to convert raster pixel coords to geo coords
        @param x_pixels x-index or x-indexes in raster units
        @param y_pixels y-index or y-indexes in raster units
        """
        if not isinstance(x_pixels, np.ndarray):
            x_pixels = np.array([x_pixels])
            y_pixels = np.array([y_pixels])
        coords = np.stack([x_pixels, y_pixels], axis=0)
        x, y = self.trtransform(coords)
        return x, y

    def raster_shape(self):
        return self._raster_data.shape

    def raster_width(self):
        return self._raster_data.shape[0]

    def raster_height(self):
        return self._raster_data.shape[1]

    def num_raster_bands(self):
        return self._raster_data.shape[2]

    def band_ranges(self, band=np.s_[:]):
        return self._band_ranges[band]

    def band_min(self, band):
        return self._band_ranges[band, 0]

    def band_max(self, band):
        return self._band_ranges[band, 1]

    def rtrot(self):
        return self._rot

    def rttranslation(self):
        return self._trans

    def raster_crs(self):
        return self._raster_crs

    def trtransform(self, a):
        return np.matmul(self.rtrot(), a) + self.rttranslation()

    def trreversetransform(self, a):
        return np.matmul(np.linalg.inv(self.rtrot()), (a - self.rttranslation()))

    def data(self, x, y, bands=np.s_[:]):
        return self._raster_data[x, y, bands]
