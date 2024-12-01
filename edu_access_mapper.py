import os
import processing
import geopandas as gpd
import numpy as np
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox, QDialog
from qgis.utils import iface
from qgis.core import (QgsProject, QgsVectorLayer, QgsDistanceArea, 
                       QgsCoordinateReferenceSystem, QgsGeometry, QgsPointXY)
from PyQt5 import uic

class SchoolDistributionAnalyzer(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.ui_path = os.path.join(self.plugin_dir, "edu_access_mapper_dialog_base.ui")
        if not os.path.exists(self.ui_path):
            raise FileNotFoundError(f"UI file not found at {self.ui_path}")
        self.dlg = uic.loadUi(self.ui_path, self)
        self.action = QAction("Analyze School Distribution", self.iface.mainWindow())
        self.action.triggered.connect(self.show_dialog)
        
        self.dlg.runButton.clicked.connect(self.run_analysis)
        self.populate_layer_combo_boxes()

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        self.action = QAction(QIcon(":/plugins/edu_access_mapper/icon.png"), "Analyze School Distribution", self.iface.mainWindow())
        self.action.triggered.connect(self.show_dialog)
        self.iface.addPluginToMenu("&School Distribution Analyzer", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.iface.removePluginMenu("&School Distribution Analyzer", self.action)
        self.iface.removeToolBarIcon(self.action)
        del self.action

    def show_dialog(self):
        """Display the plugin dialog."""
        self.populate_layer_combo_boxes()
        self.dlg.show()

    def populate_layer_combo_boxes(self):
        """Populate the ComboBox widgets with available layers."""
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                self.dlg.comboBoxSchool.addItem(layer.name(), layer.id())
                self.dlg.comboBoxCities.addItem(layer.name(), layer.id())

    def run_analysis(self):
        """Run the analysis using selected layers."""
        school_layer_id = self.dlg.comboBoxSchool.currentData()
        cities_layer_id = self.dlg.comboBoxCities.currentData()

        school_layer = QgsProject.instance().mapLayer(school_layer_id)
        cities_layer = QgsProject.instance().mapLayer(cities_layer_id)

        if not (school_layer and cities_layer):
            QMessageBox.warning(self, "Missing Layers", "Please select both the school and cities layers.")
            return

        try:
            analysis_results = self.analyze_school_distribution(school_layer, cities_layer)
            self.display_analysis_results(analysis_results)
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", f"An error occurred during analysis: {str(e)}")

    def analyze_school_distribution(self, school_layer, cities_layer):
        """Analyze school distribution and determine the number of required schools."""
        # Convert layers to GeoPandas DataFrames
        schools_gdf = self.layer_to_geopandas(school_layer)
        cities_gdf = self.layer_to_geopandas(cities_layer)

        # Ensure both GeoDataFrames use the same CRS
        if schools_gdf.crs != cities_gdf.crs:
            cities_gdf = cities_gdf.to_crs(schools_gdf.crs)

        # Perform spatial join to count schools in each district
        schools_with_cities = gpd.sjoin(schools_gdf, cities_gdf, how='left', predicate='within')
        schools_per_city = schools_with_cities.groupby('DIST_NAME').size()

        # Calculate required schools based on population data
        max_students_per_school = 2000
        cities_gdf['TOTAL_POP'] = cities_gdf['TOTAL_POP'].astype(float)
        cities_gdf['required_schools'] = (cities_gdf['TOTAL_POP'] / max_students_per_school).apply(np.ceil).astype(int)

        # Calculate additional schools needed
        cities_gdf['current_schools'] = cities_gdf['DIST_NAME'].map(schools_per_city).fillna(0)
        cities_gdf['additional_schools_needed'] = cities_gdf['required_schools'] - cities_gdf['current_schools']
        cities_gdf['additional_schools_needed'] = cities_gdf['additional_schools_needed'].apply(lambda x: max(x, 0))

        return {
            'total_schools': len(schools_gdf),
            'schools_per_city': schools_per_city.to_dict(),
            'required_schools': cities_gdf[['DIST_NAME', 'required_schools']].set_index('DIST_NAME').to_dict()['required_schools'],
            'additional_schools_needed': cities_gdf[['DIST_NAME', 'additional_schools_needed']].set_index('DIST_NAME').to_dict()['additional_schools_needed']
        }



    def layer_to_geopandas(self, qgis_layer):
        """Convert a QGIS vector layer to GeoPandas DataFrame."""
        return gpd.read_file(qgis_layer.source())

    def display_analysis_results(self, results):
        """Display analysis results in a user-friendly manner."""
        result_text = (
            f"Total Schools: {results['total_schools']}\n\n"
            "Schools per City:\n"
        )
        for city, count in results['schools_per_city'].items():
            result_text += f"{city}: {count} schools\n"

        result_text += "\nRequired Schools (max 2,000 students per school):\n"
        for city, required in results['required_schools'].items():
            result_text += f"{city}: {required} schools\n"

        result_text += "\nAdditional Schools Needed:\n"
        for city, additional in results['additional_schools_needed'].items():
            result_text += f"{city}: {additional} schools\n"

        QMessageBox.information(self, "School Distribution Analysis", result_text)


def classFactory(iface):
    return SchoolDistributionAnalyzer(iface)
