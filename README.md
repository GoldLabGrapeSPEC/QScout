<p>The QScout suite is a collection of interacting QGIS Processing plugins for georeferencing and analyzing field 
scouting data. The plugins are run within QGIS on imported scouting data. QGIS is a Geographic Information Systems program similar to ArcGIS. 
<ul>
<li>The <b>Pin Dropper</b> plugin takes data from a spreadsheet and puts them on a crop field.</li>
<li>The <b>Pin Locator</b> plugin takes data from a crop field and gives row and column coordinates within the field so you can understand where they are in relation to the map.</li>
<li>The <b>Value Grabber</b> plugin takes data on a map in the form of points, and attaches pixel values from a raster file to them.</li>
<li>The <b>Grid Aggregator</b> plugin takes data on a map and groups them together so you can do math on it more easily.</li>
</ul>
<p>In this documentation, parameter names are in <i>italics</i>, and code is in <code>monospaced typewriter font</code>.</p> 
<p>The program can be cloned from this repository or downloaded from the QGIS plugin manager (eventually). Check out <a href="https://www.youtube.com/watch?v=aD0VHeCq8gU">this tutorial</a> for instructions on how to use the plugin manager.</p>

<h1>Drop Pins / Locate Pins in Field</h1>
<h2>Abstract</h2>
<p>Drop Pins (Processing: <code>qscout:droppins</code>) is a plugin for georeferencing field data with a particular focus on vinyards. The plugin can also be used to drop points on a field if no data is available.</p>
<p>Locate Pins in Field (Processing: <code>qscout:locatepinsinfield</code>) effectively does the opposite of Drop Pins. Given a vector layer of points, the plugin will produce a copy of the layer with row and plant numbers added.</p>
<p>These two algorithms largely use the same parameters so are grouped together.</p>
<h2>Usage Guide</h2>
<p>The minimum required to run the plugin is a <i>Bounding Polygon</i>, a <i>Row Vector</i>, and values for <i>Row Spacing</i> and <i>Point Interval</i>. The <i>Bounding Polygon</i> is the bounderies of the area which the program will drop within. It does not have to be a rectangle but can be any polygon. The <i>Row Vector</i> is a line drawn along a row. The program uses the <i>Row Vector</i> to understand the layout of the area. The program will assume all rows are parallel to the <i>Row Vector</i>. The length of the row vector does not matter, only the direction. If the row vector has more than two points, the plugin will ignore all but the first and last point.</p>
<p>In order to assign data to dropped points, Drop Pins requires an <i>Input Data</i> file. Currently, the only format supported is .csv. Excel, Google Docs, OpenOffice, and any other spreadsheet software will allow you to save files in the .csv format. The order of the columns in the file does not matter - the program will automatically search for columns with headers with names like 'Row' and 'Column' and use those to georeference the data. All other columns will be included as fields in the <i>Output Layer</i> unless you specify which fields to use with <i>Fields to Use</i> parameter. If your data describes the locations of plants in relation to the panel number in the row, use the <i>Panel Size</i> parameter to tell the plugin how many plants are in a panel. A data file is <b>not</b> required for Locate Pins in Field.</p>
<p>Locate Pins in Field requires <i>Points to Index</i>, which is a vector layer</p>
<p>The <i>Start Corner</i> parameter helps the program understand how row and plant numbers translate to points on a map. The corners of the field are determined from the <i>Row Vector</i>, which is assumed to point right to left. On a clock face, if the first point of the row vector is at the center of the clock, the last point of the row vector is at 3:00 (right), and top, bottom, and left are at 12:00, 6:00, and 9:00 respectively.</p>
<p>The <i>Raster Layer</i>, <i>Match Threshold</i> and <i>Rate Offset Match Function</i> allow the program to drop points in a 'smarter' way. If <i>Rate Offset Match Function</i> is set to a value other than Regular, the program will attempt to find plants using the provided <i>Raster Layer</i>.</p>

<h2>Parameters Reference</h2>
<h3>Basic Parameters</h3>
<ul>
<li><i>Targeting Raster</i> (Processing: <code>TARGETING_RASTER_INPUT</code>): The input raster for the program. Not required if <i>Rate Offset Match Function</i> is set to 'Regular'. IMPORTANT: the input raster must have the same CRS as the <i>Bounding Polygon</i></li>
<li><i>Bounding Polygon</i> (Processing: <code>BOUND_POLYGON_INPUT</code>): A layer containing a polygon that the program will drop pins within.</li>
<li><i>Row Vector</i> (Processing: <code>ROW_VECTOR_INPUT</code>): A direction vector, which the program takes in the form of a line, representing a row in the field. The first point in the line is the start point for the field, so this is also implicitly a position vector. Don't overthink this - just find a place where the raster is a clear pattern and draw a line along a row. If the CRS is different from BOUND_POLYGON_INPUT it will be automatically converted.</li>
<li><i>Input Data</i> (Processing: <code>DATA_SOURCE_INPUT</code>): A csv file containing the data to georeference. If no file is provided, the program will drop a pin on everything it thinks is a plant. If a file is provided, the program will only drop pins on features described in the file.<br>Only used by Drop Pins.</li>
<li><i>Drop Data-Less Points</i> (Processing: <code>DROP_DATALESS_POINTS_INPUT</code>): Whether the program will drop points on plants that don't have any information provided in <i>Input Data</i>. If <i>Input Data</i> is not provided, this will be treated as True.<br>Only used by Drop Pins.</li>
<li><i>Row Spacing</i> (Processing: <code>ROW_SPACING_INPUT</code>): The distance between two rows, in the units of the CRS used by <i>Bounding Polygon</i>.</li>
<li><i>Point Interval</i> (Processing: <code>POINT_INTERVAL_INPUT</code>): The interval between points on a row. Functions similar to row height.</li>
<li><i>Match Threshold</i> (Processing: <code>OVERLAY_MATCH_THRESHOLD_INPUT</code>): A value from 0.000 to 1.000. The threshold at which to declare an overlay box a match and drop a pin. How this number is applied depends on which <i>Rating Function</i> has been selected. The default value is completely arbitrary and has absolutely no mathematical or scientific significance.</li>
<li><i>Start Corner</i> (Processing: <code>START_CORNER_INPUT</code>): The corner of the field where the numbering starts. You would find row 1, plant 1 in this corner. For a better understanding of what "Top", "Bottom", "Left", and "Right" mean in this context, see the Usage Guide.</li>
<li><i>Points to Index</i> (Processing: <code>POINTS_INPUT</code>): In Locate Pins in Field, the pins to assign row and plant number values to.<br>Only used by Locate Pins in Field.</li>
<li><i>Dropped Pins</i> (Processing: <code>DROPPED_PINS_OUTPUT</code>): The layer or file where the program will output the dropped points. Leave blank to generate a new layer.<br>Only for Drop Pins.</li>
<li><i>Indexed Points</i> (Processing: <code>INDEXED_POINTS_OUTPUT</code>): The layer or file where the program will output the points with field coordinates (row, plant). Only for Locate Pins in Field.</li>
</ul>

<h3>Advanced Parameters</h3>
<ul>
<li><i>Rate Offset Match Function</i> (Processing: <code>RATE_OFFSET_MATCH_FUNCTION_INPUT</code>: the function used to identify points as plants. See the Advanced Use Guide for more information.</li>
<li><i>Compare from Root</i> (Processing: <code>COMPARE_FROM_ROOT_INPUT</code>): If set to True, the <i>Rate Offset Match Function></i> will use the root point (the one at the beginning of the <i>Row Vector</i> for comparisons rather than a neighboring point.</li>
<li><i>Fields to Use</i> (Processing: <code>DATA_SOURCE_FIELDS_TO_USE</code>): A comma-seperated list of the columns in the csv provided in <i>Input Data</i> to express as fields in the features in the <i>Output Layer</i>. If left blank, all columns will be converted to <i>Output Layer</i> fields.<br>Only for Drop Pins.</li>
<li><i>Panel Size</i> (Processing: <code>PANEL_SIZE_INPUT</code>): The size of the panels in the field. Used for analysis of <i>Input Data</i>. For more information, see the Advanced Use Guide.<br>Only for Drop Pins.</li>
<li><i>Overlay Box Radius</i> (Processing: <code>OVERLAY_BOX_RADIUS_INPUT</code>): the radius of the box that the program will use for its comparisons, in field units (i.e. the height and interval values specified in the above section). Defaults to 2, which means 2 units AROUND the spot where the program is considering dropping a pin.</li>
<li><i>Maximum Patch Size</i> (Processing: <code>PATCH_SIZE_INPUT</code>): The largest size of hole to fill when patching holes. I'm not explaining this very well. Set to 0 for no hole patching.</li>
<li><i>Row Spacing Stdev</i> (Processing: <code>ROW_SPACING_STDEV_INPUT</code>): the standard deviation of the row height values. The program will assume a gaussian distribution and look within three standard deviations.</li>
<li><i>Point Interval Stdev</i> (Processing: <code>POINT_INTERVAL_STDEV_INPUT</code>): the standard deviation of the interval between points on a row. The program will assume a gaussian distribution and look within three standard deviations.</li>
<li><i>Search Iteration Size</i> (Processing: <code>SEARCH_ITERATION_SIZE_INPUT</code>): The size of the sides of the search box used when searching an area to drop a pin, in points. The number of points checked per iteration will be this value squared. The side lengths in crs units are determined by the <i>Row Spacing Stdev</i> and <i>Point Interval Stdev</i>. Increasing this value will exponentially increase search time, porportionally to <i>Number of Search Iterations</i>. Has no significance when using the <i>Rate Offset Match Function</i> 'Regular'.</li>
<li><i>Number of Search Iterations</i> (Processing: <code>SEARCH_NUM_ITERATIONS_INPUT</code>): The number of times the program will zoom in on an area and search in greater detail when attempting to drop a pin. Increasing this value may increase precision but will also increase execution time linearly in proportion to the square of <i>Search Iteration Size</i>. Has no significance when using the <i>Rate Offset Match Function</i> 'Regular'.</li>
<li><i>Precision Bias Coefficient</i> (Processing: <code>PRECISION_BIAS_COEFFICIENT_INPUT</code>): If nonzero, the result of <i>Rate Offset Match Function</i> will be divided by this value times the square of the deviation from the expected location when dropping pins. A higher value will cause the program to favor dropping pins near where it expects them to be. For more information, see the Advanced Use Guide. Has no significance when using the <i>Rate Offset Match Function</i> 'Regular'.</li>
</ul>

<h2>Advanced Use Guide</h2>
More advanced guide coming soon
<h3>Rating Functions</h3>
All these functions were developed by me. I'd be very interested to see what an actual expert would come up with.<Br>
<b>Regular</b>: This is the default rating function. It ignores any provided <i>Raster Layer</i> and drops points at regular intervals. It's by far the fastest rating function because it doesn't actually do any rating.<br>
<b>Local Normalized Difference</b>: Each pixel value for each raster band is "normalized" by dividing it by the range of values for that band within the <b>sample</b>. The average difference between normalized values in the two samples is compared to get the match value.<br>
<b>Global Normalized Difference</b>: Each pixel value for each raster band is "normalized" by dividing it by the range of values for that band within the <b>entire raster</b>. The average difference between normalized values in the two samples is compared to get the match value.<br
<b>Absolute Difference</b>: The average difference between the two samples is divided by 255.<br>
<b>Relative Match Count</b>: Counts the number of pixels where the normalized values in the two samples are within 0.1 of each other. The count of relative matches is divided by the total number of pixels in the sample.<br>
<b>Gradients</b>: The program calculates how much the pixel values are changing at each pixel, for each band. (Should the gradients be calculated based on normalized samples?) The average difference between the two gradient matrices is divided by 255. This is by far the most computaitonally intensive of the rating functions.<br>
<b>Random</b>: Drops points randomly within the <i>Row Spacing Stdev</i> and <i>Point Interval Stdev</i>. I wrote this function during the development process to test if the other functions perform better than random chance, and have included it here on the off chance that someone may find an application for it.<br>

<h2>FAQ</h2>

<h2>Troubleshooting</h2>
<b>Problem:</b> "My (1,1) point isn't in the correct corner."<br>
<b>Solution:</b> You may have drawn the row vector in the opposite direction from what you meant. The row vector points left to right towards what would be 3:00 on a clock face. To fix this problem, you can either redraw the row vector or imagine that the entire map is rotated by 180 degrees. <br>
<br>
<b>Problem:</b> "Error message reading 'ValueError: some errors were detected!' followed by a series of messages reading something akin to 'Line #<i>x</i> (got <i>y</i> columns instead of <i>z</i>)'."<br>
<b>Solution:</b> The first step is to check that your lines all have the same number of values. The <code>.csv</code> file can be opened in a text editor. Every row should have the same number of values, seperated by commas. If that doesn't work, check if your column headers have any special characters, such as "$", "#", "%", and remove those characters if you find them. If that doesn't solve the problem, email me. 
<br>
<b>Problem:</b> "Empty data values from some columns in my input csv file are set to -1 as attributes."<br>
<b>Solution:</b> In your spreadsheet software, set any value in the column causing the problem to a decimal, e.g. <code>10</code> becomes <code>10.0</code>. You don't need to do this for every value in the column, just one.<br>
<br>
Let me know if you have any more questions, which will then become 'frequently asked'


<h1>Grid Aggregator</h1>
<h2>Abstract</h2>
<p>This program takes a point layer and creates a polygon layer grid, then sets the values of the cells of the grid based on which points
fall within the borders. The grid will be oriented along the axes of the CRS of the points layer. (I think this always means N/S/E/W? Do some CRSs use other axes?)</p>

<h2>Parameter Reference</h2>
<h3>Basic Parameters</h3>
<ul>
<il><i>Points</i> (Processing: <code>POINTS_INPUT</code>): The points to aggregate in the grid.</il>
<li><i>Grid Cell Width</i> (Processing: <code>GRID_CELL_W_INPUT</code>): The width of the grid cells.</li>
<li><i>Grid Cell Height</i> (Processing: <code>GRID_CELL_H_INPUT</code>): The height of the grid cells.</li>
<li><i>Fields to Use</i> (Processing: <code>FIELDS_TO_USE_INPUT</code>): The fields to aggregate in the grid. Each field will be seperately aggregated.</li>
<li><i>Aggregation Function</i> (Processing: <code>AGGREGATION_FUNCTION_INPUT</code>): The function to use to aggregate the values into the grid. Most of the options are likely self-explainatory but a detailed description can be found in the Advanced Use Guide.</li>
<li><i>Aggregate Grid</i> (Processing: <code>AGGREGATE_GRID_OUTPUT</code>): The output file or layer where the grid will be created.</li>
</ul>
<h3>Advanced Parameters</h3>
<ul>
<li><i>Custom Aggregation Function</i> (Processing: <code>CUSTOM_AGGREGATION_FUNCTION_INPUT</code>): A file containing a custom aggregation function. Only for use by people experianced with Python. An example custom aggregation function script with more notes can be found in this repository, named <code>example_aggregate_function.py</code>.</li>
<li><i>Grid Extent</i> (Processing: <code>GRID_EXTENT_INPUT</code>): Optional: the extent to draw the grid. An extent specified with an alternative CRS will be automatically converted. If left unspecified, grid extent will be automatically calculated from the extent of the <i>Points</i> parameter.</li>
</ul>

<h2>Advanced Use Guide</h2>
<h3>Aggregation Functions</h3>
<p>The built-in aggregation functions are <b>Mean Average</b>, <b>Median Average</b>, <b>Sum</b>, <b>Standard Deviation</b>, and <b>Weighted Average</b>. Most of these are pretty self-explainatory. Weighted Average returns the average of the point values weighted by the distance between the point and the center of the grid cell. (I'm going to need to explain this better at some point)</p>
<p>In addition to the built-in aggregation functions, python-savvy users can pass the plugin a custom aggregation function. This is explored in the next section.</p>

<h3>Custom Aggregation Functions</h3>
<p>If the user would like to aggregate pin values using a mathematical method not included in the prepackaged aggregation functions, they can specify their own custom aggregation function by passing a python file in the <i>Custom Aggregation Function</i> parameter.</p>
<p>A custom aggregation function python file should contain a class named <code>Aggregator</code> which implements the following functions:</p>
<ul>
<li><code>__init__(self, context)</code> The processing plugin will pass itself to the constructor so that the aggregation function wrapper object can query attributes of the processing plugin.</li>
<li><code>manual_field_ag(self)</code>, a function which returns a constant boolean value which is <code>False</code> if the aggregation function will return modified versions of the fields in the point layer passed to the plugin and <code>True</code> if the aggregation function will flatly return values for the fields specified in <code>self.return_vals()</code>. I'm not explaining this very well.</li>
<li><code>return_vals(self)</code>, a function which takes no arguements and returns a list of length at least 1, containing 2-length tuples. Each tuple should contain the name of a field that this aggregation function will produce and the datatype, as a QVariant field type (<code>QVariant.Int</code>, <code>QVariant.Double</code>, or <code>QVariant.String</code>).</li>
<li><code>aggregate(self, cell)</code>, the function that actually aggregates point values. This function accepts an instance of <code>GridGrabberCell</code> (for details on <code>GridGrabberCell</code>, see below) and, if <code>self.manual_field_ag()</code> is <code>False</code>, should return a list with length <code>len(self.return_vals()) * cell.attr_count())</code>. If <code>self.manual_field_ag()</code> is <code>True</code>, the list should be of the same length as <code>self.return_vals()</code> and ordered in the same way.</li>
</ul>
Tip: if you run the program and there are no errors but the Attribute Table in QGIS is empty, you probably passed something the wrong data type.

<h1>Value Grabber</h1>
<h2>Parameter Reference</h2>
<h3>Basic Parameters</h3>
<ul>
<li><i>Points Input</i> (Processing: <code>POINTS_INPUT</code>): A vector layer of points. The layer will be duplicated and the duplicate will be returned with added fields for the bands of the raster.</li>
<li><i>Raster File Input</i> (Processing: <code>RASTER_INPUT</code>): The raster file to grab band values from. In order to facilitate the use of large datasets which might crash QGIS, the file does NOT have to be a QGIS layer in the open project.</li>
<li><i>Points with Grabbed Values</i> (Processing: <code>POINTS_WITH_VALUES_OUTPUT</code>): The points layer that will be returned. Can be a new layer or a file.</li>
</ul>
<h3>Advanced Parameters</h3>
<ul>
<li><i>Grab Radius</i> (Processing: <code>GRAB_RADIUS_INPUT</code>): Optional. If specified, the plugin will assign each point the average raster value within a radius. </li>
<li><i>Grab Area Distance Weight</i> (Processing: <code>GRAB_AREA_DISTANCE_WEIGHT_INPUT</code>): Optional. If this is specified, the average taken within <i>Grab Radius</i> will be weighted by <code>1 / (distance from point^2 * <i>Grab Area Distance Weight</i>)</code>. The raster value directly below the point will be assigned a weight of <code>1</code>.</li>
<li><i>Grab Function</i> (Processing: <code>GRAB_FUNCTION_INPUT</code>): Optional. If specified, a custom python script that will be used to grab values from the raster. Recommended for advanced users only. See <b>Advanced Use</b> below.</li>
</ul>
<h2>Advanced Use</h2>
<h3>Custom Grab Functions</h3>
<p>Similarly to in <b>Grid Aggregator</b>, the user can pass the algorithm a python script with a custom function to grab the values to assign to the features. Unlike <b>Grid Aggregator</b>, a custom script for <b>Value Grabber</b> contains only a single function without a class wrapper. The function should be have signature <code>def grab(coords, distances, bands, pixels, center_geo, center_raster, point_feature, context)</code>, where:</p>
<ul>
<li><code>coords</code> is a pair of lists of raster coords around <code>center_raster</code> and within <code>context.get_pixel_radius_around(center_geo)</code>. Can be unpacked with <code>xs, ys = coords</code>.</li>
<li><code>distances</code> is a numpy array of the distance of each coord pair in <code>coords</code> from <code>center_raster</code>, in pixel units.</li>
<li><code>bands</code> is the bands to return values for. It takes the form of a boolean array the length of which is the number of bands.</li>
<li><code>pixels</code> is a one-dimensional numpy array of values of pixels at the points specified in <code>coords</code>.</li>
<li><code>center_geo</code> is the point at and/or around which the function will grab, in geographic coordinates, as an x,y tuple.</li>
<li><code>center_raster</code> the point at and/or around which the function will grab, in the crs units of the raster, as an x,y tuple.</li>
<li><code>point_feature</code> the QgsFeature instance (point) that shows the location being grabbed. useful if you want the grab function to use attributes of the feature.</li>
<li><code>context</code> is the instance of <code>QScoutValueGrabberAlgorithm</code> which is executing this algorithm.</li>
</ul>