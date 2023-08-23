from napari_matplotlib.base import NapariMPLWidget
from matplotlib.widgets import SpanSelector
import numpy as np
from cmap import Colormap
from napari.utils import colormaps
from microfilm import colorify
from matplotlib_scalebar.scalebar import ScaleBar

def plot_spectral_profile(rgb_image, index_image, index_name, format_dict, scale=1,
                          location="", fig=None, roi=None):


    left_right_margin_fraction = format_dict['left_right_margin_fraction']
    bottom_top_margin_fraction = format_dict['bottom_top_margin_fraction']
    plot_image_w_fraction = format_dict['plot_image_w_fraction']
    font_factor = format_dict['font_factor']
    color_plotline = format_dict['color_plotline']
    plot_thickness = format_dict['plot_thickness']
    figure_size_factor = format_dict['figure_size_factor']
    scale_font_size = format_dict['scale_font_size']
    index_colormap = format_dict['index_colormap']
    red_conrast_limits = format_dict['red_conrast_limits']
    green_conrast_limits = format_dict['green_conrast_limits']
    blue_conrast_limits = format_dict['blue_conrast_limits']


    # get colormap
    if index_name in index_colormap.keys():
        newmap = Colormap(colormaps.ALL_COLORMAPS[index_colormap[index_name]].colors)
    else:
        newmap = Colormap(colormaps.ALL_COLORMAPS['viridis'].colors)
    mpl_map = newmap.to_matplotlib()

    rgb_to_plot = rgb_image.copy()
    rgb_to_plot, _, _, _ = colorify.multichannel_to_rgb(
        rgb_to_plot,
        cmaps=['pure_red', 'pure_green', 'pure_blue'], 
        rescale_type='limits', 
        limits=[red_conrast_limits, green_conrast_limits, blue_conrast_limits],
        proj_type='sum')

    # The plot has the same height as the image and 6 times the width
    # Two two images take 1 width and the plot 4
    # In addition there are margins on all sides, specified in fractions of the image dimesions
    # The axes are added in fractions of the figure dimensions. It is made sure
    # that the axes fille the space of the full figure minus the margins
    im_w = index_image.shape[1]
    im_h = index_image.shape[0]
    width_tot = (2 + plot_image_w_fraction) *im_w

    to_add_top = bottom_top_margin_fraction*im_h
    to_add_bottom = bottom_top_margin_fraction*im_h
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
    fig_size = figure_size_factor*np.array([width_tot_margin, height_tot_margin]) / height_tot_margin
    fig.clear()
    fig.set_size_inches(fig_size)
    fig.set_facecolor('white')
    ax1 = fig.add_axes(rect=(left_margin,bottom_margin,quarter, im_h / height_tot_margin))
    ax2 = fig.add_axes(rect=(quarter+left_margin,bottom_margin,quarter,im_h / height_tot_margin))
    ax3 = fig.add_axes(rect=(2*quarter+left_margin, bottom_margin, plot_image_w_fraction*quarter, im_h / height_tot_margin))

    ax1.imshow(rgb_to_plot, aspect='auto')
    vmin = np.percentile(index_image, 0.1)
    vmax = np.percentile(index_image, 99.9)
    #ax2.imshow(index_image, vmin=vmin, vmax=vmax, aspect='auto', cmap=mpl_map)
    ax2.imshow(index_image, aspect='auto', cmap=mpl_map)
    scalebar = ScaleBar(scale, "mm", 
                        length_fraction=0.25, location='lower right',
                        font_properties={'size': scale_font_size}
                        )
    scalebary = ScaleBar(scale, "mm", 
                            length_fraction=0.25, location='lower left', rotation='vertical',
                            font_properties={'size': scale_font_size}
                            )

    ax1.add_artist(scalebar)
    ax1.add_artist(scalebary)

    if roi is not None:
        colmin = int(roi[0,1])
        colmax = int(roi[3,1])
        roi = np.concatenate([roi, roi[[0]]])
        ax2.plot(roi[:,1], roi[:,0], 'r')
    else:
        colmin = 0
        colmax = index_image.shape[1]
    
    proj = index_image[:,colmin:colmax].mean(axis=1)
    ax3.plot(proj, np.arange(len(proj)),
                color=np.array(color_plotline),
                linewidth=plot_thickness)
        

    ax3.set_ylim(0, len(proj))
    ax3.yaxis.tick_right()
    ax3.invert_yaxis()
    
    # set y axis scale
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
    fig.suptitle(index_name + '\n' + location,
                    fontsize=int(font_factor*im_h))

    return fig, ax1, ax2, ax3

class SpectralPlotter(NapariMPLWidget):
    """Subclass of napari_matplotlib NapariMPLWidget for voxel position based time series plotting.
    This widget contains a matplotlib figure canvas for plot visualisation and the matplotlib toolbar for easy option
    controls. The widget is not meant for direct docking to the napari viewer.
    Plot visualisation is triggered by moving the mouse cursor over the voxels of an image layer while holding the shift
    key. The first dimension is handled as time. This widget needs a napari viewer instance and a LayerSelector instance
    to work properly.
    Attributes:
        axes : matplotlib.axes.Axes
        selector : napari_time_series_plotter.LayerSelector
        cursor_pos : tuple of current mouse cursor position in the napari viewer
    """
    def __init__(self, napari_viewer, options=None):
        super().__init__(napari_viewer)
        self.axes = self.canvas.figure.subplots()
        self.cursor_pos = np.array([])
        self.axes.tick_params(colors='white')
       

    def clear(self):
        """
        Clear the canvas.
        """
        #self.axes.clear()
        pass

class SelectRange:
    
    def __init__(self, parent, ax, single=False):
        
        self.ax = ax
        self.single = single
        self.canvas = ax.figure.canvas
        self.parent = parent
        self.myline1 = None
        self.myline2 = None
        self.min_pos = None
        self.max_pos = None
        
        self.span = SpanSelector(ax, onselect=self.onselect, direction='horizontal',
                                 interactive=True, props=dict(facecolor='blue', alpha=0.5))#, button=1)
        

    def onselect(self, min_pos, max_pos):
        
        if self.myline1 is not None:
            self.myline1.pop(0).remove()
        if self.myline2 is not None:
            self.myline2.pop(0).remove()
        
        min_max = [self.ax.lines[0].get_data()[1].min(),
                   self.ax.lines[0].get_data()[1].max()]

        self.myline2 = self.ax.plot([max_pos, max_pos], min_max, 'r')
        if not self.single:
            self.myline1 = self.ax.plot([min_pos, min_pos], min_max, 'r')
            self.min_pos = min_pos
        
        self.max_pos = max_pos
        
    def disconnect(self):
        self.span.disconnect_events()
        self.canvas.draw_idle()