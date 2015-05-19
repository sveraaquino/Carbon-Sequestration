# -*- coding: utf-8 -*-
"""
/***************************************************************************
 carbonoCompare
                                 A QGIS plugin
 Permite estimar el secuestro de carbono entre dos fechas 
                              -------------------
        begin                : 2015-03-12
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Santiago Vera
        email                : sveraaquino@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.utils import iface
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QAction, QIcon, QMessageBox
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from carbono_compare_dialog import carbonoCompareDialog
from qgis.core import *
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
import os.path
from PyQt4.QtCore import QFileInfo
from PyQt4.QtGui import *
from qgis.gui import *
import numpy
from osgeo import gdal
import numpy.ma as ma
from numpy import zeros
from numpy import logical_and


class carbonoCompare:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'carbonoCompare_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = carbonoCompareDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Secuestro de carbono')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'carbonoCompare')
        self.toolbar.setObjectName(u'carbonoCompare')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('carbonoCompare', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/carbonoCompare/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Secuestro de carbono'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Secuestro de carbono'),
                action)
            self.iface.removeToolBarIcon(action)


    def __normalizacion(self,bandCom,stdBase,meanBase,stdCom,meanCom):
        """Realiza la normalizacion radiometrica entre dos bandas"""

        n=meanBase-meanCom*stdBase/stdCom
        m=stdBase/stdCom
        bandCom=m*bandCom+n
        return bandCom


    def run(self):
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.show()
        layers = QgsMapLayerRegistry.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.RasterLayer:
                self.dlg.layerBaseIRCombo.addItem(layer.name(), layer)
                self.dlg.layerBaseRojoCombo.addItem(layer.name(), layer)
                self.dlg.layerComIRCombo.addItem(layer.name(), layer)
                self.dlg.layerComRojoCombo.addItem(layer.name(), layer)

        # Run the dialog event loop
        result = self.dlg.exec_()
        self.iface.mainWindow().statusBar().showMessage( u"Calculando" )
        # See if OK was pressed
        if result:
            #Se extrae las capas seleccionadas para el calculo de NDVI
            index = self.dlg.layerBaseIRCombo.currentIndex()
            irBaseLayer=self.dlg.layerBaseIRCombo.itemData(index)
            index = self.dlg.layerBaseRojoCombo.currentIndex()
            rojoBaseLayer=self.dlg.layerBaseRojoCombo.itemData(index)


            index = self.dlg.layerComIRCombo.currentIndex()
            irComLayer=self.dlg.layerComIRCombo.itemData(index)
            index = self.dlg.layerComRojoCombo.currentIndex()
            rojoComLayer=self.dlg.layerComRojoCombo.itemData(index)


            inDs = gdal.Open(irBaseLayer.source())
            driver = inDs.GetDriver()
            bandBaseIrc = inDs.GetRasterBand(1)
            bandBaseIrc=bandBaseIrc.ReadAsArray()
            bandBaseIrc=bandBaseIrc.astype(numpy.float)



            inDs = gdal.Open(irComLayer.source())
            driver = inDs.GetDriver()
            bandComIrc = inDs.GetRasterBand(1)
            bandComIrc=bandComIrc.ReadAsArray()
            bandComIrc=bandComIrc.astype(numpy.float)


            inDs = gdal.Open(rojoBaseLayer.source())
            driver = inDs.GetDriver()
            bandBaseRojo = inDs.GetRasterBand(1)
            bandBaseRojo=bandBaseRojo.ReadAsArray()
            bandBaseRojo=bandBaseRojo.astype(numpy.float)


            inDs = gdal.Open(rojoComLayer.source())
            driver = inDs.GetDriver()
            bandComRojo = inDs.GetRasterBand(1)
            bandComRojo=bandComRojo.ReadAsArray()
            bandComRojo=bandComRojo.astype(numpy.float)


            path="/home/santiago/ndvi.tif"
            outDataset = driver.Create(str(path),inDs.RasterXSize,inDs.RasterYSize,1,gdal.GDT_Float32)


            inDs = gdal.Open(rojoComLayer.source())
            driver = inDs.GetDriver()
            mascaraDeCambio = inDs.GetRasterBand(1)
            mascaraDeCambio=mascaraDeCambio.ReadAsArray()
            #zeramos nuestra matriz de cambio
            #decremento=2,incremento=1,no cambio=0
            mascaraDeCambio[mascaraDeCambio==mascaraDeCambio]=1
            iterar=True

            #inicializamos los parametros estadisticos para la primera iteracion
            stdBaseIrc = bandBaseIrc.std()
            meanBaseIrc = bandBaseIrc.mean()
            stdComIrc = bandComIrc.std()
            meanComIrc = bandComIrc.mean()


            stdBaseRojo = bandBaseRojo.std()
            meanBaseRojo = bandBaseRojo.mean()
            stdComRojo = bandComRojo.std()
            meanComRojo = bandComRojo.mean()

            difA = bandBaseIrc - bandBaseRojo
            difA[difA==0]=-1.0
            sumA = bandBaseIrc + bandBaseRojo
            sumA[sumA==0]=-1.0
            ndviBase= difA / sumA
            meanAnterior=1.0

            indice=0
            while iterar:
                indice=indice+1

                print "iteacion= "+str(indice)
                print stdBaseIrc
                print meanBaseIrc
                print stdComIrc
                print meanComIrc
                bandircNorm=self.__normalizacion(bandComIrc,stdBaseIrc,meanBaseIrc,stdComIrc,meanComIrc)
                print "---------------------------------------"
                print stdBaseRojo
                print meanBaseRojo
                print stdComRojo
                print meanComRojo
                bandredNorm=self.__normalizacion(bandComRojo,stdBaseRojo,meanBaseRojo,stdComRojo,meanComRojo)


                difA = bandircNorm - bandredNorm
                difA[difA==0]=-1.0

                sumA = bandircNorm + bandredNorm
                sumA[sumA==0]=-1.0

                del bandredNorm
                del bandircNorm

                ndviCom = difA / sumA

                del difA
                del sumA

                """
                ndviChange= 1.0 * (ndviCom*100/ndviBase)

                #1=perdida: 2=ganancia: 3=igual
                ndviChange[ndviChange<80.0]=1.0
                ndviChange[ndviChange>120.0]=2.0
                ndviChange[(ndviChange!=1.0) & (ndviChange!=2.0)]=3.0


                ndviBase[(ndviBase > 0.3) & (ndviBase < 0.8)]=1.0
                ndviBase[ndviBase != 1.0]= 0.0

                ndviCom[(ndviCom > 0.41572) & (ndviCom < 0.730062)]=1.0
                ndviCom[ndviCom !=1.0 ]= 0.0


                maskForestTemp=ndviBase + ndviCom


                maskForestTemp[maskForestTemp > 1.0]=1.0

                del ndviCom
                del ndviBase


                resultado=maskForestTemp * ndviChange

                print "Informe del Analisis"
                print "Perdida de Vegetacion :" +str(resultado[resultado == 1].size*30.0/10000)+" has."
                print "Aumento de Vegetacion :" +str(resultado[resultado == 2].size*30.0/10000)+" has."
                print "Conservacion de Vegetacion :" +str(resultado[resultado == 3].size*30.0/10000)+" has."
                print "Superficie analizada: "+str(resultado.size*30.0/10000)+" has."

                print "------------------------------------"

                iterar=False

                """

                difNdvi= ndviCom - ndviBase
                divMean = 1.0*(difNdvi.mean()*100/meanAnterior)


                meanAnterior = difNdvi.mean()
                desviacion = difNdvi.std()
                media = difNdvi.mean()
                n = 1
                umbralDer = media + n * desviacion
                umbralIzq = media - n * desviacion
                difNdvi[difNdvi > umbralDer]= 1
                difNdvi[difNdvi < umbralIzq]= 2 
                difNdvi[(difNdvi != 1) & (difNdvi != 2)]= 3

                #print difMean
                print divMean
                #if 1==1:
                if (indice != 1) & ((divMean < 1.0) | ((divMean > 100.0) & (divMean < 101.0))):
                    ndviBase[(ndviBase > 0.3) & (ndviBase < 0.8)]=1.0
                    ndviBase[ndviBase != 1.0]= 0.0

                    ndviCom[(ndviCom > 0.3) & (ndviCom < 0.8)]=1.0
                    ndviCom[ndviCom !=1.0 ]= 0.0


                    maskForestTemp=ndviBase + ndviCom
                    del ndviCom
                    del ndviBase

                    maskForestTemp[maskForestTemp > 1.0]=1.0
                    resultado=maskForestTemp * difNdvi

                    iterar = False
                else:
                    difNdvi[difNdvi == 3] = 0

                    del ndviCom

                    #calcular los parametros estadisticos de la normalizacion para cada banda
                    """mx = ma.masked_array(bandBaseIrc,mask=difNdvi)
                    stdBaseIrc = mx.std()
                    meanBaseIrc = mx.mean()
                    del mx"""

                    mx = ma.masked_array(bandComIrc,mask=difNdvi)
                    stdComIrc = mx.std()
                    meanComIrc = mx.mean()
                    del mx

                    """
                    mx = ma.masked_array(bandBaseRojo,mask=difNdvi)
                    stdBaseRojo = mx.std()
                    meanBaseRojo = mx.mean()
                    del mx"""

                    mx = ma.masked_array(bandComRojo,mask=difNdvi)
                    stdComRojo = mx.std()
                    meanComRojo = mx.mean()
                    del mx


            #print (difNdvi ==1).sum()
            #print (difNdvi ==2).sum()
            #print (difNdvi ==3).sum()

            outDataset.SetGeoTransform(inDs.GetGeoTransform())
            outDataset.SetProjection(inDs.GetProjection())

            outband = outDataset.GetRasterBand(1)
            outband.SetNoDataValue(-99)
            outband.WriteArray(resultado)
            outband.FlushCache()


            band = outDataset.GetRasterBand(1)


            colDic={'Blanco':'#ffffff','Rojo':'#ff0000', 'Verde':'#00ff00','Azul':'#0000ff'}

            valueList =[2, 1, 3,0]
            lst = [ QgsColorRampShader.ColorRampItem(valueList[0], QColor(colDic['Verde'])), \
            QgsColorRampShader.ColorRampItem(valueList[1], QColor(colDic['Rojo'])), \
            QgsColorRampShader.ColorRampItem(valueList[3], QColor(colDic['Blanco'])), \
            QgsColorRampShader.ColorRampItem(valueList[2], QColor(colDic['Azul']))]

            myRasterShader = QgsRasterShader()
            myColorRamp = QgsColorRampShader()

            myColorRamp.setColorRampItemList(lst)
            myColorRamp.setColorRampType(QgsColorRampShader.INTERPOLATED)
            myRasterShader.setRasterShaderFunction(myColorRamp)




            # insert the output raster into QGIS interface
            outputRasterFileInfo = QFileInfo(str(path))
            baseName = outputRasterFileInfo.baseName()
            rasterLayer = QgsRasterLayer(str(path), baseName)

            myPseudoRenderer = QgsSingleBandPseudoColorRenderer(\
            rasterLayer.dataProvider(), rasterLayer.type(),  myRasterShader)

            rasterLayer.setRenderer(myPseudoRenderer)

            if not rasterLayer.isValid():
                print "Layer failed to load"
            QgsMapLayerRegistry.instance().addMapLayer(rasterLayer)

            iface.legendInterface().refreshLayerSymbology(rasterLayer)

            #QMessageBox.information(None, 'Raster Scale',"Min %s : Max %s" % ( band1.mean() , bandNorm.mean()))
            #QMessageBox.information(None, 'Rasssssss',"Min %s : Max %s" % ( band1.std() , bandNorm.std()))
            #QMessageBox.information(None, 'Rasasdfasdfs',"Min %s : Max %s" % ( band1.std(),numpy.array_equal(band1,bandNorm)))


            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass
