# -*- coding: utf-8 -*-
"""
/***************************************************************************
 carbonoCompare
                                 A QGIS plugin
 Permite estimar el secuestro de carbono entre dos fechas 
                             -------------------
        begin                : 2015-03-12
        copyright            : (C) 2015 by Santiago Vera
        email                : sveraaquino@gmail.com
        git sha              : $Format:%H$
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


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load carbonoCompare class from file carbonoCompare.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .carbono_compare import carbonoCompare
    return carbonoCompare(iface)
