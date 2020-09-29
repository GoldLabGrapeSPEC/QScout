# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PinDropper
                                 A QGIS plugin
 Drops pins on semi-regular patterns
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2020-09-29
        copyright            : (C) 2020 by Joshua Evans
        email                : joshuaevanslowell@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""

__author__ = 'Joshua Evans'
__date__ = '2020-09-29'
__copyright__ = '(C) 2020 by Joshua Evans'


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load PinDropper class from file PinDropper.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .pin_dropper import PinDropperPlugin
    return PinDropperPlugin()
