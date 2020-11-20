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
        self.rot = np.array(self.raster_transform)[np.array([1, 2, 4, 5])].reshape(2, 2)
        self.trans = np.array(self.raster_transform)[np.array([0, 3])].reshape(2, 1)
        del ds  # save memory

    def as_raster_coords(self, x_geo, y_geo, crs_transform=None):
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
        x, y = np.matmul(np.linalg.inv(self.rot), (coords - self.trans))
        if x.shape[0] == 1:
            return int(round(x[0])), int(round(y[0]))  # "int(round(...)) is redundant but the program gets mad if I don't
        else:
            return x.astype(np.int_), y.astype(np.int_)

    def as_geo(self, x_pixels, y_pixels):
        if not isinstance(x_pixels, np.ndarray):
            x_pixels = np.array([x_pixels])
            y_pixels = np.array([y_pixels])
        coords = np.stack([x_pixels, y_pixels], axis=0)
        x, y = np.matmul(self.rot, coords) + self.trans
        return x, y

    def num_raster_bands(self):
        return self.raster_data.shape[2]

    def data(self, x, y, bands=np.s_[:]):
        return self.raster_data[x, y, bands]
