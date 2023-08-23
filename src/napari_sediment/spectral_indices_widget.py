from pathlib import Path
from dataclasses import asdict
import numpy as np
import matplotlib.pyplot as plt
from qtpy.QtWidgets import (QVBoxLayout, QPushButton, QWidget,
                            QLabel, QFileDialog, QSpinBox,
                            QComboBox, QLineEdit, QSizePolicy,
                            QGridLayout, QCheckBox, QDoubleSpinBox,
                            QColorDialog)
from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap, QColor
from superqt import QLabeledDoubleRangeSlider
import pandas as pd
from microfilm import colorify
from cmap import Colormap
from matplotlib_scalebar.scalebar import ScaleBar
from napari_matplotlib.base import NapariMPLWidget

from .parameters import Param
from .parameters_endmembers import ParamEndMember
from .io import load_project_params, load_endmember_params, load_plots_params
from .imchannels import ImChannels
from .sediproc import find_index_of_band
from .spectralplot import SpectralPlotter
from .channel_widget import ChannelWidget
from .spectralindex import SpectralIndex
from .rgb_widget import RGBWidget
from .parameters_plots import Paramplot

from napari_guitils.gui_structures import TabSet, VHGroup


class SpectralIndexWidget(QWidget):
    """Widget for the SpectralIndices."""
    
    def __init__(self, napari_viewer):
        super().__init__()
        
        self.viewer = napari_viewer

        self.rgb = [640, 545, 460]

        self.index_triplets = []
        self.create_index_list()

        self.params = Param()
        self.params_indices = ParamEndMember()
        self.params_plots = Paramplot()

        self.ppi_boundary_lines = None
        self.end_members = None
        self.index_file = None

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.tab_names = ["Main", "Indices", "IO", "ROI", "Plots", "Plotslive"]
        self.tabs = TabSet(self.tab_names, tab_layouts=[None, QGridLayout(), None, None, QGridLayout(), None])

        self.main_layout.addWidget(self.tabs)

        self.btn_select_export_folder = QPushButton("Select project folder")
        self.export_path_display = QLineEdit("No path")
        self.tabs.add_named_tab('Main', self.btn_select_export_folder)
        self.tabs.add_named_tab('Main', self.export_path_display)
        self.btn_load_project = QPushButton("Load project")
        self.tabs.add_named_tab('Main', self.btn_load_project)
        self.qlist_channels = ChannelWidget(self)
        self.tabs.add_named_tab('Main', self.qlist_channels)

        self.rgbwidget = RGBWidget(self)
        self.tabs.add_named_tab('Main', self.rgbwidget.rgbmain_group.gbox)

        # indices tab
        self._create_indices_tab()
        tab_rows = self.tabs.widget(1).layout().rowCount()
        self.ppi_plot = SpectralPlotter(napari_viewer=self.viewer)
        self.tabs.add_named_tab('Indices', self.ppi_plot, grid_pos=(tab_rows, 0, 1, 3))
        self.ppi_boundaries_range = QLabeledDoubleRangeSlider(Qt.Orientation.Horizontal)
        self.ppi_boundaries_range.setValue((0, 0, 0))
        self.tabs.add_named_tab('Indices', self.ppi_boundaries_range, grid_pos=(tab_rows+1, 0, 1, 3))
        self.btn_create_index = QPushButton("New index")
        self.tabs.add_named_tab('Indices', self.btn_create_index, grid_pos=(tab_rows+2, 0, 1, 1))
        self.qtext_new_index_name = QLineEdit()
        self.tabs.add_named_tab('Indices', self.qtext_new_index_name, grid_pos=(tab_rows+2, 1, 1, 2))
        self.btn_update_index = QPushButton("Update current index")
        self.tabs.add_named_tab('Indices', self.btn_update_index, grid_pos=(tab_rows+3, 0, 1, 1))

        self.btn_compute_RABD = QPushButton("Compute Index")
        self.tabs.add_named_tab('Indices', self.btn_compute_RABD, grid_pos=(tab_rows+4, 0, 1, 3))

        # IO tab
        self.index_pick_group = VHGroup('Indices', orientation='G')
        self.index_pick_group.glayout.setAlignment(Qt.AlignTop)
        self.tabs.add_named_tab('IO', self.index_pick_group.gbox)
        self._create_index_io_pick()
        self.btn_export_index_settings = QPushButton("Export index settings")
        self.tabs.add_named_tab('IO', self.btn_export_index_settings)
        self.btn_import_index_settings = QPushButton("Import index settings")
        self.tabs.add_named_tab('IO', self.btn_import_index_settings)
        self.index_file_display = QLineEdit("No file selected")
        self.tabs.add_named_tab('IO', self.index_file_display)
        #self.btn_select_index_file = QPushButton("Select index file")
        #self.tabs.add_named_tab('IO', self.btn_select_index_file)

        self.spin_roi_width = QSpinBox()
        self.spin_roi_width.setRange(1, 1000)
        self.spin_roi_width.setValue(20)
        self.tabs.add_named_tab('ROI', self.spin_roi_width)

        #self.index_plot = SpectralPlotter(napari_viewer=self.viewer)
        #self.tabs.add_named_tab('Plots', self.index_plot)

        self.pixlabel = QLabel()
        self.pixlabel.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        self.pixlabel.setScaledContents(True)

        #self.index_plot_live = SpectralPlotter(napari_viewer=self.viewer)
        self.index_plot_live = NapariMPLWidget(napari_viewer=self.viewer)
        self.index_plot_live.figure.set_layout_engine('none')
        self.tabs.add_named_tab('Plotslive', self.index_plot_live)

        #self.pixlabel.resizeEvent = self._on_resize_preview
        self.tabs.add_named_tab('Plots', self.pixlabel)
        self.btn_create_index_plot = QPushButton("Create index plot")
        self.tabs.add_named_tab('Plots', self.btn_create_index_plot, grid_pos=(1, 0, 1, 2))
        self.spin_left_right_margin_fraction = QDoubleSpinBox()
        self.spin_left_right_margin_fraction.setRange(0, 100)
        self.spin_left_right_margin_fraction.setValue(0.1)
        self.spin_left_right_margin_fraction.setSingleStep(0.1)
        self.tabs.add_named_tab('Plots', QLabel('L/R Margin fraction'), grid_pos=(2, 0, 1, 1))
        self.tabs.add_named_tab('Plots', self.spin_left_right_margin_fraction, grid_pos=(2, 1, 1, 1))
        self.spin_bottom_top_margin_fraction = QDoubleSpinBox()
        self.spin_bottom_top_margin_fraction.setRange(0, 100)
        self.spin_bottom_top_margin_fraction.setValue(0.05)
        self.spin_bottom_top_margin_fraction.setSingleStep(0.01)
        self.tabs.add_named_tab('Plots', QLabel('B/T Margin fraction'), grid_pos=(3, 0, 1, 1))
        self.tabs.add_named_tab('Plots', self.spin_bottom_top_margin_fraction, grid_pos=(3, 1, 1, 1))
        self.spin_plot_image_w_fraction = QDoubleSpinBox()
        self.spin_plot_image_w_fraction.setRange(0, 100)
        self.spin_plot_image_w_fraction.setValue(0.25)
        self.spin_plot_image_w_fraction.setSingleStep(0.1)
        self.tabs.add_named_tab('Plots', QLabel('Plot width fraction'), grid_pos=(4, 0, 1, 1))
        self.tabs.add_named_tab('Plots', self.spin_plot_image_w_fraction, grid_pos=(4, 1, 1, 1))
        self.spin_font_factor = QDoubleSpinBox()
        self.spin_font_factor.setRange(0, 100)
        self.spin_font_factor.setValue(0.5)
        self.spin_font_factor.setSingleStep(0.1)
        self.tabs.add_named_tab('Plots', QLabel('Font factor'), grid_pos=(5, 0, 1, 1))
        self.tabs.add_named_tab('Plots', self.spin_font_factor, grid_pos=(5, 1, 1, 1))
        self.qcolor_plotline = QColorDialog()
        self.btn_qcolor_plotline = QPushButton("Select plot line color")
        self.tabs.add_named_tab('Plots', self.btn_qcolor_plotline, grid_pos=(6, 0, 1, 2))
        self.qcolor_plotline.setCurrentColor(Qt.blue)
        self.spin_plot_thickness = QDoubleSpinBox()
        self.spin_plot_thickness.setRange(1, 10)
        self.spin_plot_thickness.setValue(1)
        self.spin_plot_thickness.setSingleStep(0.1)
        self.tabs.add_named_tab('Plots', QLabel('Plot line thickness'), grid_pos=(7, 0, 1, 1))
        self.tabs.add_named_tab('Plots', self.spin_plot_thickness, grid_pos=(7, 1, 1, 1))
        #self.btn_reset_figure_size = QPushButton("Reset figure size")
        #self.tabs.add_named_tab('Plots', self.btn_reset_figure_size, grid_pos=(9, 0, 1, 2))
        self.spin_figure_size_factor = QDoubleSpinBox()
        self.spin_figure_size_factor.setRange(1, 100)
        self.spin_figure_size_factor.setValue(1)
        self.spin_figure_size_factor.setSingleStep(1)
        self.tabs.add_named_tab('Plots', QLabel('Figure size factor'), grid_pos=(8, 0, 1, 1))
        self.tabs.add_named_tab('Plots', self.spin_figure_size_factor, grid_pos=(8, 1, 1, 1))
        self.spin_scale_font_size = QSpinBox()
        self.spin_scale_font_size.setRange(1, 100)
        self.spin_scale_font_size.setValue(1)
        self.spin_scale_font_size.setSingleStep(1)
        self.tabs.add_named_tab('Plots', QLabel('Scale font size'), grid_pos=(9, 0, 1, 1))
        self.tabs.add_named_tab('Plots', self.spin_scale_font_size, grid_pos=(9, 1, 1, 1))
        self.btn_save_plot = QPushButton("Save plot")
        self.tabs.add_named_tab('Plots', self.btn_save_plot, grid_pos=(10, 0, 1, 2))

        self.btn_save_plot_params = QPushButton("Save plot parameters")
        self.tabs.add_named_tab('Plots', self.btn_save_plot_params, grid_pos=(11, 0, 1, 2))
        self.btn_load_plot_params = QPushButton("Load plot parameters")
        self.tabs.add_named_tab('Plots', self.btn_load_plot_params, grid_pos=(12, 0, 1, 2))

        
        self._connect_spin_bounds()
        self.add_connections()

    def _create_indices_tab(self):

        self.current_index_type = 'RABD'

        self.indices_group = VHGroup('Indices', orientation='G')
        self.tabs.add_named_tab('Indices', self.indices_group.gbox, [1, 0, 1, 3])

        self.qcom_indices = QComboBox()
        self.qcom_indices.addItems([value.index_name for key, value in self.index_collection.items()])
        self.spin_index_left, self.spin_index_right, self.spin_index_middle= [self._spin_boxes() for _ in range(3)]
        self.indices_group.glayout.addWidget(self.qcom_indices, 0, 0, 1, 1)
        self.indices_group.glayout.addWidget(self.spin_index_left, 1, 0, 1, 1)
        self.indices_group.glayout.addWidget(self.spin_index_middle, 1, 1, 1, 1)
        self.indices_group.glayout.addWidget(self.spin_index_right, 1, 2, 1, 1)
        

    def _spin_boxes(self, minval=0, maxval=1000):
        """Create a spin box with a range of minval to maxval"""
        
        spin = QSpinBox()
        spin.setRange(minval, maxval)
        return spin
          
    def create_index_list(self):

        index_def = {
            'RABD510': [470, 510, 530],
            'RABD660670': [590, 665, 730],
        }
        self.index_collection = {}
        for key, value in index_def.items():
            self.index_collection[key] = SpectralIndex(index_name=key,
                              index_type='RABD',
                              left_band_default=value[0],
                              middle_band_default=value[1],
                              right_band_default=value[2]
                              )
            
        index_def = {
            'RABA410560': [410, 560],
        }
        for key, value in index_def.items():
            self.index_collection[key] = SpectralIndex(index_name=key,
                              index_type='RABA',
                              left_band_default=value[0],
                              right_band_default=value[1]
                              )
            
        index_def = {
            'R590R690': [590, 690],
            'R660R670': [660, 670]
        }
        for key, value in index_def.items():
            self.index_collection[key] = SpectralIndex(index_name=key,
                              index_type='Ratio',
                              left_band_default=value[0],
                              right_band_default=value[1]
            )

    def add_connections(self):
        """Add callbacks"""

        self.btn_select_export_folder.clicked.connect(self._on_click_select_export_folder)
        self.btn_load_project.clicked.connect(self.import_project)
        self.ppi_boundaries_range.valueChanged.connect(self._on_change_ppi_boundaries)
        self.btn_compute_RABD.clicked.connect(self._on_click_compute_index)
        self.btn_create_index.clicked.connect(self._on_click_new_index)
        self.btn_update_index.clicked.connect(self._on_click_update_index)
        self.qcom_indices.activated.connect(self._on_change_index_index)
        self.btn_export_index_settings.clicked.connect(self._on_click_export_index_settings)
        self.btn_import_index_settings.clicked.connect(self._on_click_import_index_settings)
        #self.btn_select_index_file.clicked.connect(self._on_click_select_index_file)
        self.btn_create_index_plot.clicked.connect(self.create_index_plot)
        
        self.connect_plot_formatting()
        self.btn_qcolor_plotline.clicked.connect(self._on_click_open_plotline_color_dialog)
        self.btn_save_plot.clicked.connect(self._on_click_save_plot)
        #self.btn_reset_figure_size.clicked.connect(self._on_click_reset_figure_size)
        self.btn_save_plot_params.clicked.connect(self._on_click_save_plot_parameters)
        self.btn_load_plot_params.clicked.connect(self._on_click_load_plot_parameters)

        self.viewer.mouse_double_click_callbacks.append(self._add_analysis_roi)

    def _connect_spin_bounds(self):

        self.spin_index_left.valueChanged.connect(self._on_change_spin_bounds)
        self.spin_index_middle.valueChanged.connect(self._on_change_spin_bounds)
        self.spin_index_right.valueChanged.connect(self._on_change_spin_bounds)

    def _disconnect_spin_bounds(self):
            
        self.spin_index_left.valueChanged.disconnect(self._on_change_spin_bounds)
        self.spin_index_middle.valueChanged.disconnect(self._on_change_spin_bounds)
        self.spin_index_right.valueChanged.disconnect(self._on_change_spin_bounds)

    def _on_change_spin_bounds(self, event=None):

        self.ppi_boundaries_range.setValue(
            (self.spin_index_left.value(), self.spin_index_middle.value(),
              self.spin_index_right.value()))
    
    def _on_click_select_export_folder(self, event=None, export_folder=None):
        """Interactively select folder to analyze"""

        if export_folder is None:
            self.export_folder = Path(str(QFileDialog.getExistingDirectory(self, "Select Directory")))
        else:
            self.export_folder = Path(export_folder)
        self.export_path_display.setText(self.export_folder.as_posix())

    def _on_click_select_index_file(self):
        """Interactively select folder to analyze"""

        self.index_file = Path(str(QFileDialog.getOpenFileName(self, "Select Index file")[0]))
        self.index_file_display.setText(self.index_file.as_posix())

    def import_project(self):
        """Import pre-processed project: corrected roi and mask"""
        
        if self.export_folder is None:
            self._on_click_select_export_folder()

        self.params = load_project_params(folder=self.export_folder)
        self.params_indices = load_endmember_params(folder=self.export_folder)

        self.imhdr_path = Path(self.params.file_path)

        self.mainroi = np.array([np.array(x).reshape(4,2) for x in self.params.main_roi]).astype(int)
        self.row_bounds = [self.mainroi[0][:,0].min(), self.mainroi[0][:,0].max()]
        self.col_bounds = [self.mainroi[0][:,1].min(), self.mainroi[0][:,1].max()]
        
        self.imagechannels = ImChannels(self.export_folder.joinpath('corrected.zarr'))
        self.qlist_channels._update_channel_list()

        self.get_RGB()
        self.rgbwidget.display_as_rgb()

        self.end_members = pd.read_csv(self.export_folder.joinpath('end_members.csv')).values
        self.endmember_bands = self.end_members[:,-1]
        self.end_members = self.end_members[:,:-1]

        self.ppi_boundaries_range.setRange(min=self.endmember_bands[0],max=self.endmember_bands[-1])
        self.ppi_boundaries_range.setValue(
            (self.endmember_bands[0], (self.endmember_bands[-1]+self.endmember_bands[0])/2, self.endmember_bands[-1]))
        
        self.plot_endmembers()
        self._on_change_index_index()

    def _add_analysis_roi(self, viewer=None, event=None, roi_xpos=None):
        """Add roi to layer"""
        
        min_row = 0
        max_row = self.row_bounds[1] - self.row_bounds[0]
        if roi_xpos is None:
            cursor_pos = np.rint(self.viewer.cursor.position).astype(int)
            
            new_roi = [
                [min_row, cursor_pos[2]-self.spin_roi_width.value()//2],
                [max_row,cursor_pos[2]-self.spin_roi_width.value()//2],
                [max_row,cursor_pos[2]+self.spin_roi_width.value()//2],
                [min_row,cursor_pos[2]+self.spin_roi_width.value()//2]]
        
        else:
            new_roi = [
                [min_row, roi_xpos-self.spin_roi_width.value()//2],
                [max_row,roi_xpos-self.spin_roi_width.value()//2],
                [max_row,roi_xpos+self.spin_roi_width.value()//2],
                [min_row,roi_xpos+self.spin_roi_width.value()//2]]

        
        if 'rois' not in self.viewer.layers:
            self.viewer.add_shapes(
                ndim = 2,
                name='rois', edge_color='red', face_color=np.array([0,0,0,0]), edge_width=10)
         
        self.viewer.layers['rois'].add_rectangles(new_roi, edge_color='r', edge_width=10)


    def get_RGB(self):
        
        self.rgb_ch = [np.argmin(np.abs(np.array(self.imagechannels.channel_names).astype(float) - x)) for x in self.rgb]
        self.rgb_names = [self.imagechannels.channel_names[x] for x in self.rgb_ch]
        [self.qlist_channels.item(x).setSelected(True) for x in self.rgb_ch]
        self.qlist_channels._on_change_channel_selection()

    def plot_endmembers(self, event=None):
        """Cluster the pure pixels and plot the endmembers as average of clusters."""

        self.ppi_plot.axes.clear()
        self.ppi_plot.axes.plot(self.endmember_bands, self.end_members)
        self.ppi_plot.figure.canvas.draw()

    def _on_change_ppi_boundaries(self, event=None):
        """Update the PPI plot when the PPI boundaries are changed."""
        
        #self._disconnect_spin_bounds()
        # update from interactive limit change
        if type(event) == tuple:
            current_triplet = np.array(self.ppi_boundaries_range.value(), dtype=np.uint16)
            if len(current_triplet) == 3:
                self.spin_index_left.setValue(current_triplet[0])
                self.spin_index_middle.setValue(current_triplet[1])
                self.spin_index_right.setValue(current_triplet[2])
            elif len(current_triplet) == 2:
                self.spin_index_left.setValue(current_triplet[0])
                self.spin_index_right.setValue(current_triplet[1])
            
        # update from spinbox change
        else:
            if self.current_index_type == 'RABD':
                current_triplet = [self.spin_index_left.value(), self.spin_index_middle.value(), self.spin_index_right.value()]
            else:
                current_triplet = [self.spin_index_left.value(), self.spin_index_right.value()]
            current_triplet = [float(x) for x in current_triplet]

            self.ppi_boundaries_range.setValue(current_triplet)

        if self.ppi_boundary_lines is not None:
                num_lines = len(self.ppi_boundary_lines)
                for i in range(num_lines):
                    self.ppi_boundary_lines.pop(0).remove()

        if self.end_members is not None:
            ymin = self.end_members.min()
            ymax = self.end_members.max()
            if self.current_index_type == 'RABD':
                x_toplot = current_triplet
                ymin_toplot = 3*[ymin]
                ymax_toplot = 3*[ymax]
            else:
                x_toplot = current_triplet
                ymin_toplot = 2*[ymin]
                ymax_toplot = 2*[ymax]
            self.ppi_boundary_lines = self.ppi_plot.axes.plot(
                [x_toplot, x_toplot],
                [
                    ymin_toplot, ymax_toplot
                ], 'r--'
            )
            self.ppi_plot.figure.canvas.draw()
        
        #self._connect_spin_bounds()

    def _update_save_plot_parameters(self):

        self.params_plots.color_plotline = [self.qcolor_plotline.currentColor().getRgb()[x]/255 for x in range(3)]
        self.params_plots.plot_thickness = self.spin_plot_thickness.value()
        self.params_plots.font_factor = self.spin_font_factor.value()
        self.params_plots.scale_font_size = self.spin_scale_font_size.value()
        self.params_plots.left_right_margin_fraction = self.spin_left_right_margin_fraction.value()
        self.params_plots.bottom_top_margin_fraction = self.spin_bottom_top_margin_fraction.value()
        self.params_plots.plot_image_w_fraction = self.spin_plot_image_w_fraction.value()
        self.params_plots.figure_size_factor = self.spin_figure_size_factor.value()

    def _on_click_save_plot_parameters(self, event=None, file_path=None):
            
        if file_path is None:
            file_path = Path(str(QFileDialog.getSaveFileName(self, "Select plot parameters file")[0]))
        self._update_save_plot_parameters()
        self.params_plots.save_parameters(file_path)

    def _on_click_load_plot_parameters(self, event=None, file_path=None):
        
        self.disconnect_plot_formatting()
        if file_path is None:
            file_path = Path(str(QFileDialog.getOpenFileName(self, "Select plot parameters file")[0]))
        self.params_plots = load_plots_params(file_path=file_path)

        self.spin_plot_thickness.setValue(self.params_plots.plot_thickness)
        self.spin_font_factor.setValue(self.params_plots.font_factor)
        self.spin_scale_font_size.setValue(self.params_plots.scale_font_size)
        self.spin_left_right_margin_fraction.setValue(self.params_plots.left_right_margin_fraction)
        self.spin_bottom_top_margin_fraction.setValue(self.params_plots.bottom_top_margin_fraction)
        self.spin_plot_image_w_fraction.setValue(self.params_plots.plot_image_w_fraction)
        self.spin_figure_size_factor.setValue(self.params_plots.figure_size_factor)
        self.qcolor_plotline.setCurrentColor(QColor(*[int(x*255) for x in self.params_plots.color_plotline]))

        self.connect_plot_formatting()
        self.create_index_plot()

    def disconnect_plot_formatting(self):

        self.spin_plot_image_w_fraction.valueChanged.disconnect(self.create_index_plot)
        self.spin_font_factor.valueChanged.disconnect(self.create_index_plot)
        self.spin_bottom_top_margin_fraction.valueChanged.disconnect(self.create_index_plot)
        self.spin_left_right_margin_fraction.valueChanged.disconnect(self.create_index_plot)
        self.qcolor_plotline.currentColorChanged.disconnect(self.create_index_plot)
        self.spin_plot_thickness.valueChanged.disconnect(self.create_index_plot)
        self.spin_figure_size_factor.valueChanged.disconnect(self.create_index_plot)
        self.spin_scale_font_size.valueChanged.disconnect(self.create_index_plot)

    def connect_plot_formatting(self):

        self.spin_bottom_top_margin_fraction.valueChanged.connect(self.create_index_plot)
        self.spin_left_right_margin_fraction.valueChanged.connect(self.create_index_plot)
        self.spin_plot_image_w_fraction.valueChanged.connect(self.create_index_plot)
        self.spin_font_factor.valueChanged.connect(self.create_index_plot)
        self.qcolor_plotline.currentColorChanged.connect(self.create_index_plot)
        self.spin_plot_thickness.valueChanged.connect(self.create_index_plot)
        self.spin_figure_size_factor.valueChanged.connect(self.create_index_plot)
        self.spin_scale_font_size.valueChanged.connect(self.create_index_plot)


    def create_index_plot(self, event=None):
        """Create the index plot."""

        self._update_save_plot_parameters()

        left_right_margin_fraction = self.spin_left_right_margin_fraction.value()
        top_bottom_margin_fraction = self.spin_bottom_top_margin_fraction.value()
        # w space occupied by plot e.g. 0.25 mean plot takes has a width a quarter
        # of the image width
        plot_image_w_fraction = self.spin_plot_image_w_fraction.value()
        font_factor = self.spin_font_factor.value()

        if self.qcom_indices.currentText() not in self.viewer.layers:
            self._on_click_compute_index(event=None)
        toplot = self.viewer.layers[self.qcom_indices.currentText()].data
        toplot[toplot == np.inf] = 0

        # get colormap
        newmap = Colormap(self.viewer.layers[self.qcom_indices.currentText()]._colormap.colors)
        mpl_map = newmap.to_matplotlib()

        rgb_to_plot = self.viewer.layers['imcube'].data.copy()
        rgb_to_plot = [self.viewer.layers[c].data for c in ['red', 'green', 'blue']]
        rgb_to_plot, _, _, _ = colorify.multichannel_to_rgb(
            rgb_to_plot,
            cmaps=['pure_red', 'pure_green', 'pure_blue'], 
            rescale_type='limits', 
            limits=[self.viewer.layers[c].contrast_limits for c in ['red', 'green', 'blue']],
            proj_type='sum')

        # The plot has the same height as the image and 6 times the width
        # Two two images take 1 width and the plot 4
        # In addition there are margins on all sides, specified in fractions of the image dimesions
        # The axes are added in fractions of the figure dimensions. It is made sure
        # that the axes fille the space of the full figure minus the margins
        im_w = toplot.shape[1]
        im_h = toplot.shape[0]
        width_tot = (2 + plot_image_w_fraction) *im_w

        to_add_top = top_bottom_margin_fraction*im_h
        to_add_bottom = top_bottom_margin_fraction*im_h
        to_add_left = left_right_margin_fraction * width_tot
        to_add_right = left_right_margin_fraction * width_tot

        # width_tot_margin 
        # = 6 * im_w + (2*left_right_margin_fraction) * 6 * im_w 
        # = 6 * im_w (1 + 2*left_right_margin_fraction)
        width_tot_margin = width_tot + to_add_left + to_add_right
        height_tot_margin = im_h + to_add_top + to_add_bottom
        # left_margin = (0.25 * 6*im_w) / (9*im_w) = 0.5/3 * im_w
        left_margin = to_add_left / width_tot_margin
        bottom_margin = to_add_bottom / height_tot_margin

        # quarter = (im_w) / (9*im_w) = 1/9
        quarter = im_w / width_tot_margin

        # The figure and axes are set explicitly to make sure that the axes fill the figure
        # This is achieved using the add_axes method instead of subplots
        self.fig_size = self.spin_figure_size_factor.value()*np.array([width_tot_margin, height_tot_margin]) / height_tot_margin
        self.index_plot_live.figure.clear()
        #fig = self.index_plot_live.figure
        self.index_plot_live.figure.set_size_inches(self.fig_size)
        self.index_plot_live.figure.set_facecolor('white')
        #fig = plt.figure(figsize=fig_size)
        ax1 = self.index_plot_live.figure.add_axes(rect=(left_margin,bottom_margin,quarter, im_h / height_tot_margin))
        ax2 = self.index_plot_live.figure.add_axes(rect=(quarter+left_margin,bottom_margin,quarter,im_h / height_tot_margin))
        ax3 = self.index_plot_live.figure.add_axes(rect=(2*quarter+left_margin, bottom_margin, plot_image_w_fraction*quarter, im_h / height_tot_margin))

        ax1.imshow(rgb_to_plot, aspect='auto')
        vmin = np.percentile(toplot, 0.1)
        vmax = np.percentile(toplot, 99.9)
        #ax2.imshow(toplot, vmin=vmin, vmax=vmax, aspect='auto', cmap=mpl_map)
        ax2.imshow(toplot, aspect='auto', cmap=mpl_map)
        scalebar = ScaleBar(self.params.scale, "mm", 
                            length_fraction=0.25, location='lower right',
                            font_properties={'size': self.spin_scale_font_size.value()}
                            )
        scalebary = ScaleBar(self.params.scale, "mm", 
                             length_fraction=0.25, location='lower left', rotation='vertical',
                             font_properties={'size': self.spin_scale_font_size.value()}
                             )

        ax1.add_artist(scalebar)
        ax1.add_artist(scalebary)

        if 'rois' in self.viewer.layers:
            roi = self.viewer.layers['rois'].data[0]
            colmin = int(roi[0,1])
            colmax = int(roi[3,1])
            proj = toplot[:,colmin:colmax].mean(axis=1)
            ax3.plot(proj, np.arange(len(proj)),
                     color=np.array(self.qcolor_plotline.currentColor().getRgb())[0:3]/255,
                     linewidth=self.spin_plot_thickness.value())
            roi = np.concatenate([roi, roi[[0]]])
            ax2.plot(roi[:,1], roi[:,0], 'r')

            ax3.set_ylim(0, len(proj))
            ax3.yaxis.tick_right()
            ax3.invert_yaxis()
        
        # set y axis scale
        scale = self.params.scale #mm/px
        tickpos = np.array([x.get_position()[1] for x in  ax1.get_yticklabels()])[1:-1]
        newlabels = scale * np.array(tickpos)
        ax1.set_yticks(ticks=tickpos, labels = newlabels)

        ax1.set_xticks([])
        ax2.set_xticks([])
        ax2.set_yticks([])
        for label in (ax1.get_yticklabels() + ax3.get_yticklabels() + ax3.get_xticklabels()):
            label.set_fontsize(int(font_factor*im_h))
        
        ax2.set_ylim(len(proj),0)
        ax1.set_ylabel('depth [mm]', fontsize=int(font_factor*im_h))
        self.index_plot_live.figure.suptitle(self.qcom_indices.currentText() + '\n' + self.params.location,
                     fontsize=int(font_factor*im_h))
        #fig.text(x=0, y=0, s='test')

        self.index_plot_live.figure.savefig(
            self.export_folder.joinpath('temp.png'),
            dpi=100, bbox_inches="tight")

        # update napari preview
        self.pixmap = QPixmap(self.export_folder.joinpath('temp.png').as_posix())
        if self.pixlabel.size().height() < self.pixlabel.size().width():
            self.pixlabel.setPixmap(self.pixmap.scaledToWidth(self.pixlabel.size().width()))
        else:
            self.pixlabel.setPixmap(self.pixmap.scaledToHeight(self.pixlabel.size().height()))

        self.ax1 = ax1
        self.ax2 = ax2
        self.ax3 = ax3

        #self.index_plot_live.figure.canvas.draw()
        #self.index_plot_live.figure.canvas.flush_events()

        #vsize = self.viewer.window.geometry()
        #self.viewer.window.resize(vsize[2]-10,vsize[3]-10)
        #self.viewer.window.resize(vsize[2],vsize[3])

    def _on_click_reset_figure_size(self, event=None):
        """Reset figure size to default"""

        self.index_plot_live.figure.set_size_inches(self.fig_size)
        self.index_plot_live.figure.canvas.draw()
        self.index_plot_live.figure.canvas.flush_events()

        vsize = self.viewer.window.geometry()
        self.viewer.window.resize(vsize[2]-10,vsize[3]-10)
        self.viewer.window.resize(vsize[2],vsize[3])

    def _on_click_save_plot(self, event=None, export_file=None):
        
        if export_file is None:
            export_file = self.export_folder.joinpath(self.qcom_indices.currentText()+'_index_plot.png')
        self.index_plot_live.figure.savefig(
            fname=export_file, dpi=500, bbox_inches="tight")

    def _on_click_open_plotline_color_dialog(self, event=None):
        """Show label color dialog"""
        
        self.qcolor_plotline.show()

    def _on_adjust_font_size(self, event=None):

        im_h = self.viewer.layers['imcube'].data.shape[-2]
        font_factor = self.spin_font_factor.value()
        for label in (self.ax1.get_yticklabels() + 
                      self.ax3.get_yticklabels() + 
                      self.ax3.get_xticklabels()):
            label.set_fontsize(int(font_factor*im_h))

        self.index_plot_live.figure.suptitle(self.qcom_indices.currentText() + '\n' + self.params.location,
                     fontsize=int(font_factor*im_h))

        self.index_plot_live.canvas.draw()

    def _on_click_new_index(self, event):
        """Add new custom index"""

        current_bands = np.array(self.ppi_boundaries_range.value(), dtype=np.uint16)
        name = self.qtext_new_index_name.text()
        if self.current_index_type == 'RABD':
            self.index_collection[name] = SpectralIndex(index_name=name,
                              index_type='RABD',
                              left_band_default=current_bands[0],
                              middle_band_default=current_bands[1],
                              right_band_default=current_bands[2]
                              )
            
        elif self.current_index_type == 'RABA':
            self.index_collection[name] = SpectralIndex(index_name=name,
                              index_type='RABA',
                              left_band_default=current_bands[0],
                              right_band_default=current_bands[1],
                              )
        elif self.current_index_type == 'ratio':
            self.index_collection[name] = SpectralIndex(index_name=name,
                              index_type='ratio',
                              left_band_default=current_bands[0],
                              right_band_default=current_bands[1],
                              )
        
        self.qcom_indices.addItem(name)
        self.qcom_indices.setCurrentText(name)

        ## add box to pick
        num_boxes = len(self.index_collection)
        self.index_pick_group.glayout.addWidget(QLabel(name), num_boxes, 0, 1, 1)
        newbox = QCheckBox()
        self.index_pick_boxes[name] = newbox
        self.index_pick_group.glayout.addWidget(newbox, num_boxes, 1, 1, 1)
        

    def _on_click_update_index(self, event):
        """Update the current index."""

        current_bands = np.array(self.ppi_boundaries_range.value(), dtype=np.uint16)
        name = self.qcom_indices.currentText()
        
        if self.current_index_type == 'RABD':
            self.index_collection[name].left_band = current_bands[0]
            self.index_collection[name].right_band = current_bands[2]
            self.index_collection[name].middle_band = current_bands[1]
        else:
            self.index_collection[name].left_band = current_bands[0]
            self.index_collection[name].right_band = current_bands[1]
            self.index_collection[name].middle_band = None            
            

    def _on_click_compute_index(self, event):
        
        if self.current_index_type == 'RABD':
            rabd_indices = self.compute_index_RABD(
                left=self.spin_index_left.value(),
                trough=self.spin_index_middle.value(),
                right=self.spin_index_right.value())
            self.viewer.add_image(rabd_indices, name=self.qcom_indices.currentText(), colormap='viridis', blending='additive')
        elif self.current_index_type == 'RABA':
            raba_indices = self.compute_index_RABA(
                left=self.spin_index_left.value(),
                right=self.spin_index_right.value())
            self.viewer.add_image(raba_indices, name=self.qcom_indices.currentText(), colormap='viridis', blending='additive')
        elif self.current_index_type == 'Ratio':
            ratio_indeces = self.compute_index_ratio(
                left=self.spin_index_left.value(),
                right=self.spin_index_right.value())
            self.viewer.add_image(ratio_indeces, name=self.qcom_indices.currentText(), colormap='viridis', blending='additive')
        else:
            print('index type: {self.current_index_type}')

    def compute_index_RABD(self, left, trough, right):
        """Compute the index RAB."""

        ltr = [left, trough, right]
        # find indices from the end-members plot (in case not all bands were used
        ltr_endmember_indices = [find_index_of_band(self.endmember_bands, x) for x in ltr]
        # find band indices in the complete dataset
        ltr_stack_indices = [find_index_of_band(self.imagechannels.centers, x) for x in ltr]

        # number of bands between edges and trough
        X_left = ltr_endmember_indices[1]-ltr_endmember_indices[0]
        X_right = ltr_endmember_indices[2]-ltr_endmember_indices[1]

        # load the correct bands
        roi = np.concatenate([self.row_bounds, self.col_bounds])
        ltr_cube = self.imagechannels.get_image_cube(
            channels=ltr_stack_indices, roi=roi)
        ltr_cube = ltr_cube.astype(np.float32)

        # compute indices
        RABD = ((ltr_cube[0] * X_right + ltr_cube[2] * X_left) / (X_left + X_right)) / ltr_cube[1] 

        return RABD
    
    def compute_index_RABA(self, left, right):
        """Compute the index RAB."""

        ltr = [left, right]
        # find indices from the end-members plot (in case not all bands were used
        ltr_endmember_indices = [find_index_of_band(self.endmember_bands, x) for x in ltr]
        # find band indices in the complete dataset
        ltr_stack_indices = [find_index_of_band(self.imagechannels.centers, x) for x in ltr]
        # main roi
        roi = np.concatenate([self.row_bounds, self.col_bounds])
        # number of bands between edges and trough
        R0_RN_cube = self.imagechannels.get_image_cube(channels=ltr_stack_indices, roi=roi)
        R0_RN_cube = R0_RN_cube.astype(np.float32)
        num_bands = ltr_endmember_indices[1] - ltr_endmember_indices[0]
        line = (R0_RN_cube[1] - R0_RN_cube[0])/num_bands
        RABA_array = np.zeros((self.row_bounds[1]-self.row_bounds[0], self.col_bounds[1]-self.col_bounds[0]))
        for i in range(num_bands):
            Ri = self.imagechannels.get_image_cube(channels=[ltr_stack_indices[0]+i], roi=roi)
            Ri = Ri.astype(np.float32)
            #print(f'Ri.shape: {Ri.shape}')
            RABA_array += ((R0_RN_cube[0] + i*line) / Ri[0] ) - 1

        return RABA_array
    
    def compute_index_ratio(self, left, right):

        ltr = [left, right]
        # find band indices in the complete dataset
        ltr_stack_indices = [find_index_of_band(self.imagechannels.centers, x) for x in ltr]
        # main roi
        roi = np.concatenate([self.row_bounds, self.col_bounds])
        numerator_denominator = self.imagechannels.get_image_cube(channels=ltr_stack_indices, roi=roi)
        numerator_denominator = numerator_denominator.astype(np.float32)
        ratio = numerator_denominator[0] / numerator_denominator[1]
        return ratio
    
    def _on_change_index_index(self, event=None):

        current_index = self.index_collection[self.qcom_indices.currentText()]
        self.current_index_type = current_index.index_type
        self.spin_index_left.setValue(current_index.left_band)
        self.spin_index_right.setValue(current_index.right_band)
        if self.current_index_type == 'RABD':
            self.spin_index_middle.setValue(current_index.middle_band)

        if self.current_index_type == 'RABD':
            self.spin_index_middle.setVisible(True)
        else:
            self.spin_index_middle.setVisible(False)

        self._on_change_ppi_boundaries()

    def _create_index_io_pick(self):
        """Create tick boxes for picking indices to export."""

        self.index_pick_boxes = {}
        for ind, key_val in enumerate(self.index_collection.items()):
            
            self.index_pick_group.glayout.addWidget(QLabel(key_val[0]), ind, 0, 1, 1)
            newbox = QCheckBox()
            self.index_pick_boxes[key_val[0]] = newbox
            self.index_pick_group.glayout.addWidget(newbox, ind, 1, 1, 1)


    def _on_click_export_index_settings(self, event=None, file_path=None):
        """Export index setttings"""

        index_series = [pd.Series(asdict(x)) for key, x in self.index_collection.items() if self.index_pick_boxes[key].isChecked()]
        index_table = pd.DataFrame(index_series)
        if file_path is None:
            file_path = Path(str(QFileDialog.getSaveFileName(self, "Select index settings file")[0]))
        if file_path.suffix != '.csv':
            file_path = file_path.with_suffix('.csv')
        index_table.to_csv(file_path, index=False)

    def _on_click_import_index_settings(self, event=None):
        """Load index settings from file."""
        
        if self.index_file is None:
            self._on_click_select_index_file()
        # clear existing state
        self.qcom_indices.clear()
        self.index_pick_boxes = {}
        self.index_collection = {}

        for i in reversed(range(self.index_pick_group.glayout.count())): 
            self.index_pick_group.glayout.itemAt(i).widget().setParent(None)

        # import table, populate combobox, export tick boxes and index_collection
        index_table = pd.read_csv(self.export_folder.joinpath('index_settings.csv'))
        index_table = index_table.replace(np.nan, None)
        for _, index_row in index_table.iterrows():
            row_dict = index_row.to_dict()
            if row_dict['middle_band'] is not None:
                row_dict['middle_band'] = int(row_dict['middle_band'])
                row_dict['middle_band_default'] = int(row_dict['middle_band_default'])
            self.index_collection[index_row.index_name] = SpectralIndex(**row_dict)
            self.index_collection[index_row.index_name].middle_bands = index_row.index_type
            self.qcom_indices.addItem(index_row.index_name)
            self.index_pick_boxes[index_row.index_name] = QCheckBox()
            self.index_pick_group.glayout.addWidget(QLabel(index_row.index_name), self.qcom_indices.count(), 0, 1, 1)
            self.index_pick_group.glayout.addWidget(self.index_pick_boxes[index_row.index_name], self.qcom_indices.count(), 1, 1, 1)
        self.qcom_indices.setCurrentText(index_row.index_name)
        self._on_change_index_index()

        


    