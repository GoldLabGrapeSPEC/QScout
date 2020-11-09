<h1>Pin Dropper</h1>
<h2>Abstract</h2>
Pin Dropper is a QGIS plugin for georeferencing field data with a particular focus on vinyards. The plugin can also be
used to drop points on a field if no data is available.
The program can be cloned from this repository or downloaded from the QGIS plugin manager (eventually)

<h2>Usage Guide</h2>


<h2>Parameters Reference</h2>
<h3>Basic Parameters</h3>
<i>Raster Layer</i> (Processing: <code>RASTER_INPUT</code>): The input raster for the program. Not required if <i>Rate Offset Match Function</i> is set to 'Regular'. IMPORTANT: the input raster must have the same CRS as the bounding <box class=""></box>
<i>Bound Box</i> (Processing: <code>BOUND_BOX_INPUT</code>): A layer containing a polygon that the program will drop pins within
<i>Row Vector</i> (Processing: <code>ROW_VECTOR_INPUT</code>): A direction vector, which the program takes in the form of a line, representing a row in the field. The first point in the line is the start point for the field, so this is also implicitly a position vector. Don't overthink this - just find a place where the raster is a clear pattern and draw a line along a row. If the CRS is different from BOUND_BOX_INPUT it will be automatically converted.
<i>Input Data</i> (Processing: <code>DATA_SOURCE_INPUT</code>): A csv file containing the data to georeference. If no file is provided, the program will drop a pin on everything it thinks is a plant. If a file is provided, the program will only drop pins on features described in the file.
<i>Drop Data-Less Points</i> (Processing: <code>DROP_DATALESS_POINTS_INPUT</code>): Whether the program will drop points on plants that don't have any information provided in <i>Input Data</i>. If <i>Input Data</i> is not provided, this will be treated as True.
<i>Row Spacing</i> (Processing: <code>ROW_HEIGHT_INPUT</code>): The distance between two rows, in the units of the CRS used by <i>Bound Box</i>
<i>Point Interval</i> (Processing: <code>POINT_INTERVAL_INPUT</code>): The interval between points on a row. Functions similar to row height.
<i>Match Threshold</i> (Processing: <code>OVERLAY_MATCH_THRESHOLD_INPUT</code>): A value from 0.000 to 1.000. The threshold at which to declare an overlay box a match and drop a pin. How this number is applied depends on which <i>Rating Function</i> has been selected. The default value is completely arbitrary and has absolutely no mathematical or scientific significance.
<i>Start Corner</i> (Processing: <code>START_CORNER_INPUT</code>): The corner of the field where the numbering starts. You would find row 1, plant 1 in this corner. For a better understanding of what "Top", "Bottom", "Left", and "Right" mean in this context, see the Usage Guide.
<i>Output Layer</i> (Processing: <code>OUTPUT</code>): the layer that the program will output geometry to. leave blank to generate a new layer

<h3>Advanced Parameters</h3>
<i>Rate Offset Match Function</i> (Processing: <code>RATE_OFFSET_MATCH_FUNCTION_INPUT</code>: the function used to identify points as plants. See the Advanced Use Guide for more information.
<i>Compare from Root</i> (Processing: <code>COMPARE_FROM_ROOT_INPUT</code>): If set to True, the <i>Rate Offset Match Function></i> will use the root point (the one at the beginning of the <i>Row Vector</i> for comparisons rather than a neighboring point.
<i>Fields to Use</i> (Processing: <code>DATA_SOURCE_FIELDS_TO_USE</code>): A comma-seperated list of the columns in the csv provided in <i>Input Data</i> to express as fields in the features in the <i>Output Layer</i>. If left blank, all columns will be converted to <i>Output Layer</i> fields.
<i>Panel Size</i> (Processing: <code>PANEL_SIZE_INPUT</code>): The size of the panels in the field. Used for analysis of <i>Input Data</i>. For more information, see the Advanced Use Guide.
<i>Overlay Box Radius</i> (Processing: <code>OVERLAY_BOX_RADIUS_INPUT</code>): the radius of the box that the program will use for its comparisons, in field units (i.e. the height and interval values specified in the above section). Defaults to 2, which means 2 units AROUND the spot where the program is considering dropping a pin.
<i>Maximum Patch Size</i> (Processing: <code>PATCH_SIZE_INPUT</code>): The largest size of hole to fill when patching holes. I'm not explaining this very well. Set to 0 for no hole patching.
<i>Row Spacing Stdev</i> (Processing: <code>ROW_HEIGHT_STDEV_INPUT</code>): the standard deviation of the row height values. The program will assume a gaussian distribution and look within three standard deviations.
<i>Point Interval Stdev</i> (Processing: <code>POINT_INTERVAL_STDEV_INPUT</code>): the standard deviation of the interval between points on a row. The program will assume a gaussian distribution and look within three standard deviations.
<i>Search Iteration Size</i> (Processing: <code>SEARCH_ITERATION_SIZE_INPUT</code>): The size of the sides of the search box used when searching an area to drop a pin, in points. The number of points checked per iteration will be this value squared. The side lengths in crs units are determined by the <i>Row Spacing Stdev</i> and <i>Point Interval Stdev</i>. Increasing this value will exponentially increase search time, porportionally to <i>Number of Search Iterations</i>. Has no significance when using the <i>Rate Offset Match Function</i> 'Regular'.
<i>Number of Search Iterations</i> (Processing: <code>SEARCH_NUM_ITERATIONS_INPUT</code>): The number of times the program will zoom in on an area and search in greater detail when attempting to drop a pin. Increasing this value may increase precision but will also increase execution time linearly in proportion to the square of <i>Search Iteration Size</i>. Has no significance when using the <i>Rate Offset Match Function</i> 'Regular'.
<i>Precision Bias Coefficient</i> (Processing: <code>PRECISION_BIAS_COEFFICIENT_INPUT</code>): If nonzero, the result of <i>Rate Offset Match Function</i> will be divided by this value times the square of the deviation from the expected location when dropping pins. A higher value will cause the program to favor dropping pins near where it expects them to be. For more information, see the Advanced Use Guide. Has no significance when using the <i>Rate Offset Match Function</i> 'Regular'.

<h2>Advanced Use Guide</h2>
More advanced guide coming soon
<h3>Rating Functions</h3>
All these functions were developed by me. I'd be very interested to see what an actual expert would come up with.
<i>Regular</i>: This is the default rating function. It ignores any provided <i>Raster Layer</i> and drops points at regular intervals. It's by far the fastest rating function because it doesn't actually do any rating.
<i>Local Normalized Difference</i>: Each pixel value for each raster band is "normalized" by dividing it by the range of values for that band within the <b>sample</b>. The average difference between normalized values in the two samples is compared to get the match value.
<i>Global Normalized Difference</i>: Each pixel value for each raster band is "normalized" by dividing it by the range of values for that band within the <b>entire raster</b>. The average difference between normalized values in the two samples is compared to get the match value.
<i>Absolute Difference</i>: The average difference between the two samples is divided by 255.
<i>Relative Match Count</i>: Counts the number of pixels where the normalized values in the two samples are within 0.1 of each other. The count of relative matches is divided by the total number of pixels in the sample.
<i>Gradients</i>: The program calculates how much the pixel values are changing at each pixel, for each band. (Should the gradients be calculated based on normalized samples?) The average difference between the two gradient matrices is divided by 255. This is by far the most computaitonally intensive of the rating functions.
<i>Random</i>: Drops points randomly within the <i>Row Spacing Stdev</i> and <i>Point Interval Stdev</i>. I wrote this function during the development process to test if the other functions perform better than random chance, and have included it here on the off chance that someone may find an application for it.

<h2>FAQ</h2>
Let me know if you have any questions, which will then become 'frequently asked'