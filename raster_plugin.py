import numpy as np
from osgeo import gdal

from qgis.core import QgsCoordinateReferenceSystem, QgsPointXY

class QScoutRasterPlugin:
    def load_raster_data(self, raster_file):
        """
        using gdal, loads raster data from file specified in parameters.
        assigns class attributes self.raster_data, self.band_ranges, and self.raster_transform
        """
        # use gdal to open raster layer
        ds = gdal.Open(raster_file)
        # oddly specific error message is oddly specific for the reason you're guessing
        assert ds is not None, "Raster layer data provider URI not accessable, or something like that."
        # create raster data array
        self.raster_data = np.stack([
            ds.GetRasterBand(band+1).ReadAsArray()
            for band
            in range(ds.RasterCount)
        ], axis=-1)

        # calculate band ranges. important for some algorithms
        self.band_ranges = np.stack([
            np.amin(self.raster_data, axis=tuple(range(len(self.raster_data.shape) - 1))),
            np.amax(self.raster_data, axis=tuple(range(len(self.raster_data.shape) - 1)))
        ], axis=-1)

        # i'm... not actually sure what's going on in this code I wrote, but it works and I'm afraid to touch it
        blank_axes = self.band_ranges[:, 0] != self.band_ranges[:, 1]
        self.raster_data = np.transpose(self.raster_data[:, :, blank_axes], axes=(1, 0, 2))
        self.band_ranges = self.band_ranges[blank_axes, :]
        self.raster_crs = QgsCoordinateReferenceSystem(ds.GetProjection())
        # save raster transform
        self.raster_transform = ds.GetGeoTransform()
        del ds  # save memory

    def as_raster_coords(self, x_geo, y_geo, crs_transform=None):
        if crs_transform is not None:
            if isinstance(x_geo, np.ndarray):
                x_geo, y_geo = crs_transform.transformCoords(numPoint=x_geo.size(), x=x_geo, y=y_geo)
            else:
                point = crs_transform.transform(QgsPointXY(x_geo, y_geo))
                x_geo = point.x()
                y_geo = point.y()
        x = (x_geo - self.raster_transform[0]) / self.raster_transform[1]
        y = (y_geo - self.raster_transform[3]) / self.raster_transform[5]

        if isinstance(x, np.ndarray):
            return x.astype(np.int_), y.astype(np.int_)
        else:
            return int(round(x)), int(round(y))  # "int(round(...)) is redundant but the program gets mad if I don't

    def as_geo(self, x_pixels, y_pixels):
        x = self.raster_transform[0] + x_pixels * self.raster_transform[1] + y_pixels * self.raster_transform[2]
        y = self.raster_transform[3] + x_pixels * self.raster_transform[4] + y_pixels * self.raster_transform[5]
        return x, y

    def num_raster_bands(self):
        return self.raster_data.shape[2]

    def data(self, x, y, bands=np.s_[:]):
        return self.raster_data[x, y, bands]
