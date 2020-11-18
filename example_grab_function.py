# This file is not used by the QScout Plugin Suite. It's provided to demonstrate a user-provided grab function
# for qscout:valuegrab. This grab function simply implements the algorithm's default grab functionality.
# To include a custom grab function, copy this file to your working directory, edit it, and then pass your edited .py
# file as the GRAB_FUNCTION_INPUT in qscout:valuegrab

import numpy as np
# all of these parameters must be in the method signature or the program will throw an error,
# but you don't have to use all of them. If you're unhappy with any part of QScoutValueGrabberAlgorithm.query_raster,
# you could technically recreate the entire function here from center_geo and bands
def grab(coords,
         distances,
         bands,
         pixels,
         center_geo,
         center_raster,
         context):
    """
    Queries raster data from an instance of QScoutValueGrabberAlgorithm, and returns a set of values to be assigned
    to a point geometry.
    This version simply returns a weighted average of values of pixels around center_geo
    @param coords a pair of lists of raster coords around center_raster and within
    context.get_pixel_radius_around(center_geo). Can be unpacked with xs, ys = coords
    @param distances a numpy array of the distance of each coord pair in coords from center_raster, in pixel units
    @param bands the bands to return values for. a boolean array the length of which is the number of bands
    @param pixels a one-dimensional numpy array of values of pixels at the points specified in coords
    @param center_geo the point at and/or around which the function will grab, in geographic coordinates
    @param center_raster the point at and/or around which the function will grab, in the crs units of the raster
    @param context an instance of QScoutValueGrabberAlgorithm
    """

    if context.grab_distance_weight() != 0:
        nanvals = np.any(np.isnan(pixels), axis=1)
        weights = 1 / ((distances ** 2) * context.grab_distance_weight())
        weights[distances == 0] = 1  # will appear as np.inf on the above line
        print(weights)
        return_data = np.average(pixels[~nanvals, :].astype(np.float_), axis=0, weights=weights[~nanvals])
    else:
        return_data = np.nanmean(pixels, axis=0)
    return return_data
