from qtpy.QtWidgets import (QComboBox, QPushButton, QWidget,
                            QLabel, QFileDialog, QListWidget, QAbstractItemView,
                            QCheckBox, QLineEdit, QSpinBox, QDoubleSpinBox,)
from qtpy.QtCore import Qt
import numpy as np
from napari_guitils.gui_structures import VHGroup, TabSet
from superqt import QDoubleRangeSlider

from .sediproc import find_index_of_band



class RGBWidget(QWidget):
    """Widget to handle channel selection and display. Works only i parent widget
    has:
    - an attribute called imagechannels, which is an instance of ImageChannels. For
    example with the SedimentWidget widget.
    - an attribute called row_bounds and col_bounds, which are the current crop
    bounds."""

    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self.viewer = parent.viewer
        self.rgb = [640, 545, 460]

        self.rgbmain_group = VHGroup('RGB', orientation='G')
        #self.tabs.add_named_tab('Main', self.rgbmain_group.gbox)

        self.rgb_bands_group = VHGroup('Select bands to display as RGB', orientation='G')
        self.rgbmain_group.glayout.addWidget(self.rgb_bands_group.gbox, 0, 0, 1, 2)

        self.btn_default_rgb = QPushButton('Default RGB')
        self.btn_default_rgb.setToolTip("Set default RGB channels")
        self.rgb_bands_group.glayout.addWidget(self.btn_default_rgb, 0, 0, 1, 6)
        self.btn_RGB = QPushButton('Load RGB')
        self.btn_RGB.setToolTip("Load RGB channels")
        self.spin_rchannel = QSpinBox()
        self.spin_rchannel.setRange(0, 1000)
        self.spin_rchannel.setValue(640)
        self.spin_gchannel = QSpinBox()
        self.spin_gchannel.setRange(0, 1000)
        self.spin_gchannel.setValue(545)
        self.spin_bchannel = QSpinBox()
        self.spin_bchannel.setRange(0, 1000)
        self.spin_bchannel.setValue(460)

        self.rgb_bands_group.glayout.addWidget(QLabel('R'), 1, 0, 1, 1)
        self.rgb_bands_group.glayout.addWidget(self.spin_rchannel, 1, 1, 1, 1)
        self.rgb_bands_group.glayout.addWidget(QLabel('G'), 1, 2, 1, 1)
        self.rgb_bands_group.glayout.addWidget(self.spin_gchannel, 1, 3, 1, 1)
        self.rgb_bands_group.glayout.addWidget(QLabel('B'), 1, 4, 1, 1)
        self.rgb_bands_group.glayout.addWidget(self.spin_bchannel, 1, 5, 1, 1)
        self.rgb_bands_group.glayout.addWidget(self.btn_RGB, 2, 0, 1, 6)

        self.rgb_layer_group = VHGroup('Select layer to display as RGB', orientation='G')
        self.rgbmain_group.glayout.addWidget(self.rgb_layer_group.gbox, 1, 0, 1, 2)

        self.combo_layer_to_rgb = QComboBox()
        self.rgb_layer_group.glayout.addWidget(QLabel('Layer to display'), 0, 0, 1, 1)
        self.rgb_layer_group.glayout.addWidget(self.combo_layer_to_rgb, 0, 1, 1, 1)
        self.btn_dislpay_as_rgb = QPushButton('Display layer as RGB')
        self.rgb_layer_group.glayout.addWidget(self.btn_dislpay_as_rgb, 1, 0, 2, 2)

        self.slider_contrast = QDoubleRangeSlider(Qt.Horizontal)
        self.slider_contrast.setRange(0, 1)
        self.slider_contrast.setSingleStep(0.01)
        self.slider_contrast.setSliderPosition([0, 1])
        self.rgbmain_group.glayout.addWidget(QLabel("RGB Contrast"), 2, 0, 1, 1)
        self.rgbmain_group.glayout.addWidget(self.slider_contrast, 2, 1, 1, 1)

        self.add_connections()

    def add_connections(self):

        self.btn_RGB.clicked.connect(self._on_click_RGB)
        self.spin_rchannel.valueChanged.connect(self._on_change_rgb)
        self.spin_gchannel.valueChanged.connect(self._on_change_rgb)
        self.spin_bchannel.valueChanged.connect(self._on_change_rgb)
        self.btn_dislpay_as_rgb.clicked.connect(self.display_as_rgb)
        self.btn_default_rgb.clicked.connect(self._set_rgb_default)
        self.slider_contrast.valueChanged.connect(self._on_change_contrast)

        self.viewer.layers.events.inserted.connect(self._update_combo_layers)
        self.viewer.layers.events.removed.connect(self._update_combo_layers)


    def _on_change_rgb(self, event=None):

        self.rgb = [self.spin_rchannel.value(), self.spin_gchannel.value(), self.spin_bchannel.value()]
    
    def _set_rgb_default(self):

        self.spin_rchannel.setValue(640)
        self.spin_gchannel.setValue(545)
        self.spin_bchannel.setValue(460)

    def _on_click_RGB(self, event=None):
        """Load RGB image"""

        self.rgb_ch = [find_index_of_band(self.parent.imagechannels.centers, x) for x in self.rgb]
        self.rgb_names = [self.parent.imagechannels.channel_names[x] for x in self.rgb_ch]

        [self.parent.qlist_channels.item(x).setSelected(True) for x in self.rgb_ch]
        self.parent.qlist_channels._on_change_channel_selection()

        rgb_indices_in_imcube = [list(self.parent.channel_indices).index(x) for x in self.rgb_ch]

        self.display_as_rgb(channels=rgb_indices_in_imcube)

    def get_current_rgb_cube(self):

        rgb_indices_in_imcube = [list(self.parent.channel_indices).index(x) for x in self.rgb_ch]
        rgb_cube = np.array([self.viewer.layers['imcube'].data[ind] for ind in rgb_indices_in_imcube])
        return rgb_cube
    
    def _on_change_contrast(self, event=None):
        """Update contrast limits of RGB channels"""
        
        rgb = ['red', 'green', 'blue']
        for c in rgb:
            contrast_limits = np.percentile(self.viewer.layers[c].data, (2,98))
            contrast_range = contrast_limits[1] - contrast_limits[0]
            newlimits = contrast_limits.copy()
            newlimits[0] = contrast_limits[0] + self.slider_contrast.value()[0] * contrast_range
            newlimits[1] = contrast_limits[0] + self.slider_contrast.value()[1] * contrast_range
            self.viewer.layers[c].contrast_limits = newlimits


    def _update_combo_layers(self):

        admit_layers = ['imcube', 'imcube_corrected', 'imcube_destripe']
        self.combo_layer_to_rgb.clear()
        for a in admit_layers:
            if a in self.viewer.layers:
                self.combo_layer_to_rgb.addItem(a)

    def display_as_rgb(self, channels=None):

        if channels is None:
            channels = [0, 1, 2]
        cmaps = ['red', 'green', 'blue']
        layer_name = self.combo_layer_to_rgb.currentText()
        for ind, cmap in zip(channels, cmaps):
            if cmap not in self.viewer.layers:
                self.viewer.add_image(
                    self.viewer.layers[layer_name].data[ind],
                    name=cmap,
                    colormap=cmap,
                    blending='additive')
            else:
                self.parent.viewer.layers[cmap].data = self.viewer.layers[layer_name].data[ind]
            
            self.viewer.layers[cmap].contrast_limits_range = (self.viewer.layers[cmap].data.min(), self.viewer.layers[cmap].data.max())
            self.viewer.layers[cmap].contrast_limits = np.percentile(self.viewer.layers[cmap].data, (2,98))
            