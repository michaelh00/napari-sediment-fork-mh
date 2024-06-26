from dataclasses import dataclass, asdict
import dataclasses
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.signal import savgol_filter
import dask.array as da
import tifffile
import cmap
import yaml

from .sediproc import find_index_of_band
from .io import load_project_params, load_plots_params, load_mask, get_mask_path
from .imchannels import ImChannels
from .spectralplot import plot_spectral_profile, plot_multi_spectral_profile

@dataclass
class SpectralIndex:
    """
    Class for keeping track of processing parameters.
    
    Parameters
    ---------
    index_name: str
        name of index
    index_type: str
        one of 'Ratio', 'RABD', 'RABA'
    left_band: int
        left band to compute index
    right_band: int
        right band to compute index
    trough_band: int
        trough band to compute index
    numerator_band: int
        numerator band to compute ratio index
    denominator_band: int
        denominator band to compute ratio index
    left_band_default: int
        default left band to compute index
    right_band_default: int
        default right band to compute index
    trough_band_default: int
        default trough band to compute index
    numerator_band_default: int
        default numerator band to compute ratio index
    denominator_band_default: int
        default denominator band to compute ratio index
    index_map: np.ndarray
        index map
    index_proj: np.ndarray
        index projection
    index_map_range: nd.array
        range of index map for plotting
    colormap: str
        colormap for index map
    
    """

    index_name: str = None
    index_type: str = None
    left_band: int = None
    right_band: int = None
    middle_band: int = None
    left_band_default: int = None
    right_band_default: int = None
    middle_band_default: int = None
    index_map: np.ndarray = None
    index_proj: np.ndarray = None
    index_map_range: np.ndarray = None
    colormap: str = 'viridis'
    
    def __post_init__(self):
        """Use defaults for bands."""

        self.left_band = self.left_band_default
        self.right_band = self.right_band_default
        self.middle_band = self.middle_band_default

    def dict_spectral_index(self):
        """Return dataclass as dict and exclude large numpy arrays."""


        dict_to_save = dataclasses.asdict(self)
        del dict_to_save['index_map']
        del dict_to_save['index_proj']
        for key in dict_to_save:
            if isinstance(dict_to_save[key], np.generic):
                dict_to_save[key] = dict_to_save[key].item()
        return dict_to_save
    

def compute_index_RABD(left, trough, right, row_bounds, col_bounds, imagechannels):
    """Compute the index RABD.
    
    Parameters
    ----------
    left: float
        left band
    trough: float
        trough band
    right: float
        right band
    row_bounds: tuple of int
        (row_start, row_end)
    col_bounds: tuple of int
        (col_start, col_end)
    imagechannels: ImageChannels
        image channels object

    Returns
    -------
    RABD: float
        RABD index
    """

    ltr = [left, trough, right]
    # find indices from the end-members plot (in case not all bands were used
    # This is not necessary as bands will not be skipped in the middle of the spectrum
    #ltr_endmember_indices = find_index_of_band(self.endmember_bands, ltr)
    # find band indices in the complete dataset
    ltr_stack_indices = find_index_of_band(imagechannels.centers,ltr)

    # number of bands between edges and trough
    #X_left = ltr_endmember_indices[1]-ltr_endmember_indices[0]
    #X_right = ltr_endmember_indices[2]-ltr_endmember_indices[1]
    X_left = ltr_stack_indices[1]-ltr_stack_indices[0]
    X_right = ltr_stack_indices[2]-ltr_stack_indices[1]

    # load the correct bands
    roi = np.concatenate([row_bounds, col_bounds])
    ltr_cube = imagechannels.get_image_cube(
        channels=ltr_stack_indices, roi=roi)
    ltr_cube = ltr_cube.astype(np.float32)+0.0000001

    # compute indices
    RABD = ((ltr_cube[0] * X_right + ltr_cube[2] * X_left) / (X_left + X_right)) / ltr_cube[1] 
    RABD = np.asarray(RABD, np.float32)
    return RABD

def compute_index_RABA(left, right, row_bounds, col_bounds, imagechannels):
    """Compute the index RABA.
    
    Parameters
    ----------
    left: float
        left band
    right: float
        right band
    row_bounds: tuple of int
        (row_start, row_end)
    col_bounds: tuple of int
        (col_start, col_end)
    imagechannels: ImageChannels
        image channels object

    Returns
    -------
    RABA: float
        RABA index
    """

    ltr = [left, right]
    # find band indices in the complete dataset
    ltr_stack_indices = [find_index_of_band(imagechannels.centers, x) for x in ltr]
    # main roi
    roi = np.concatenate([row_bounds, col_bounds])
    # number of bands between edges and trough
    R0_RN_cube = imagechannels.get_image_cube(channels=ltr_stack_indices, roi=roi)
    R0_RN_cube = R0_RN_cube.astype(np.float32)
    num_bands = ltr_stack_indices[1] - ltr_stack_indices[0]
    line = (R0_RN_cube[1] - R0_RN_cube[0])/num_bands
    RABA_array = None
    for i in range(num_bands):
        Ri = imagechannels.get_image_cube(channels=[ltr_stack_indices[0]+i], roi=roi)
        Ri = Ri.astype(np.float32) + 0.0000001
        if RABA_array is None:
            RABA_array = ((R0_RN_cube[0] + i*line) / Ri[0] ) - 1
        else:
            RABA_array += ((R0_RN_cube[0] + i*line) / Ri[0] ) - 1
    RABA_array = np.asarray(RABA_array, np.float32)
    return RABA_array
    
def compute_index_ratio(left, right, row_bounds, col_bounds, imagechannels):
    """Compute the index ratio.
        
    Parameters
    ----------
    left: float
        left band
    right: float
        right band
    row_bounds: tuple of int
        (row_start, row_end)
    col_bounds: tuple of int
        (col_start, col_end)
    imagechannels: ImageChannels
        image channels object

    Returns
    -------
    ratio: float
        ratio index
    """
    ltr = [left, right]
    # find band indices in the complete dataset
    ltr_stack_indices = [find_index_of_band(imagechannels.centers, x) for x in ltr]
    # main roi
    roi = np.concatenate([row_bounds, col_bounds])
    numerator_denominator = imagechannels.get_image_cube(channels=ltr_stack_indices, roi=roi)
    numerator_denominator = numerator_denominator.astype(np.float32)
    ratio = numerator_denominator[0] / (numerator_denominator[1] + 0.0000001)
    ratio = np.asarray(ratio, np.float32)
    return ratio

def clean_index_map(index_map):

    index_map = index_map.copy()
    index_map[index_map == np.inf] = 0
    percentiles = np.percentile(index_map, [1, 99])
    index_map = np.clip(index_map, percentiles[0], percentiles[1])
    if isinstance(index_map, da.Array):
        index_map = index_map.compute()

    return index_map

def compute_index_projection(index_image, mask, colmin, colmax, smooth_window=None):
    """Compute the projection of the index map.
    
    Parameters
    ----------
    index_map: np.ndarray
        index map
    mask: np.ndarray
        mask
    colmin: int
        minimum column
    colmax: int
        maximum column
    smooth_window: int
        window size for smoothing the projection

    Returns
    -------
    projection: np.ndarray
        projection of the index map
    """
    index_image[mask==1] = np.nan
    proj = np.nanmean(index_image[:,colmin:colmax],axis=1)

    if smooth_window is not None:
        proj = savgol_filter(proj, window_length=smooth_window, polyorder=3)


    return proj

def save_tif_cmap(image, image_path, napari_cmap, contrast):
    """Save image as tiff with colormap using specified contrast. The
    saved image is only for visualization purposes, as the values are
    rescaled and transformed to RGB.

    Parameters
    ----------
    image: np.ndarray
        image to save
    image_path: str
        path to save image
    napari_cmap: napari Colormap
        napari colormap or str
    contrast: tuple of float
        contrast

    """
    
    if isinstance(napari_cmap, str):
        current_cmap = cmap.Colormap(napari_cmap).to_matplotlib()
    else:
        current_cmap = cmap.Colormap(napari_cmap.colors).to_matplotlib()

    if contrast is None:
        contrast = (np.nanmin(image), np.nanmax(image))
    norm_image = np.clip(image, a_min=contrast[0], a_max=contrast[1])
    norm_image = (norm_image - np.nanmin(norm_image)) / (np.nanmax(norm_image) - np.nanmin(norm_image))
    
    colored_image = current_cmap(norm_image)
    colored_image = (colored_image[:, :, :3] * 255).astype(np.uint8)

    tifffile.imwrite(image_path, colored_image)

def create_index(index_name, index_type, boundaries):
    
    if index_type == 'RABD':
        new_index = SpectralIndex(index_name=index_name,
                            index_type='RABD',
                            left_band_default=boundaries[0],
                            middle_band_default=boundaries[1],
                            right_band_default=boundaries[2],
                            )
        
    elif index_type == 'RABA':
        new_index = SpectralIndex(index_name=index_name,
                            index_type='RABA',
                            left_band_default=boundaries[0],
                            right_band_default=boundaries[1],
                            )
    elif index_type == 'ratio':
        new_index = SpectralIndex(index_name=index_name,
                            index_type='ratio',
                            left_band_default=boundaries[0],
                            right_band_default=boundaries[1],
                            )
    else:
        raise ValueError('Index type not recognized.')
        
    return new_index

def export_index_series(index_series, file_path):

    index_series = [x.dict_spectral_index() for key, x in index_series.items()]
    index_series = {'index_definition': index_series}
    if file_path.suffix !='.yml':
        file_path = file_path.with_suffix('.yml')
    with open(file_path, "w") as file:
        yaml.dump(index_series, file)

def compute_index(spectral_index, row_bounds, col_bounds, imagechannels):
    """Compute the index and add to napari."""

    if spectral_index.index_type == 'RABD':
        computed_index = compute_index_RABD(
            left=spectral_index.left_band,
            trough=spectral_index.middle_band,
            right=spectral_index.right_band,
            row_bounds=row_bounds,
            col_bounds=col_bounds,
            imagechannels=imagechannels)
    elif spectral_index.index_type == 'RABA':
        computed_index = compute_index_RABA(
            left=spectral_index.left_band,
            right=spectral_index.right_band,
            row_bounds=row_bounds,
            col_bounds=col_bounds,
            imagechannels=imagechannels)
    elif spectral_index.index_type == 'Ratio':
        computed_index = compute_index_ratio(
            left=spectral_index.left_band,
            right=spectral_index.right_band,
            row_bounds=row_bounds,
            col_bounds=col_bounds,
            imagechannels=imagechannels)
    else:
        print(f'unknown index type: {spectral_index.index_type}')
        return None
    return computed_index

def load_index_series(index_file):
    """Load the index series from a yml file."""
    
    index_collection = {}
    with open(index_file) as file:
        index_series = yaml.full_load(file)
    for index_element in index_series['index_definition']:
        index_collection[index_element['index_name']] = SpectralIndex(**index_element)

    return index_collection

def batch_create_plots(project_list, index_params_file, plot_params_file, normalize=False):
    """Create index plots for a list of projects.
    
    Parameters
    ----------
    project_list: list of Path
        list of project folders (containing Parameters.yml)
    index_params_file: Path
        path to index parameters file
    plot_params_file: Path
        path to plot parameters file
    normalize: bool
        whether to save plots in normalized folder

    """

    indices = load_index_series(index_params_file)
    params_plots = load_plots_params(plot_params_file)

    for ex in project_list:

        roin_ind = 0
        dpi = 300
        
        params = load_project_params(folder=ex)
        roi_folder = ex.joinpath(f'roi_{roin_ind}')
        if normalize:
            roi_plot_folder = roi_folder.joinpath('index_plots_normalized')
            if not roi_plot_folder.exists():
                roi_plot_folder.mkdir()
        else:
            roi_plot_folder = roi_folder.joinpath('index_plots')
            if not roi_plot_folder.exists():
                roi_plot_folder.mkdir()

        mainroi = np.array([np.array(x).reshape(4,2) for x in params.main_roi]).astype(int)
        row_bounds = [
                    mainroi[roin_ind][:,0].min(),
                    mainroi[roin_ind][:,0].max()]
        col_bounds = [
                    mainroi[roin_ind][:,1].min(),
                    mainroi[roin_ind][:,1].max()]
        
        measurement_roi = None
        if len(params.measurement_roi) > 0:
            measurement_roi = np.array(params.measurement_roi).reshape(4,2).astype(int)
            colmin = measurement_roi[:,1].min()
            colmax = measurement_roi[:,1].max()
        else:
            colmin = 0
            colmax = col_bounds[1] - col_bounds[0]

        # get RGB and mask
        mask = load_mask(get_mask_path(roi_folder))
        myimage = ImChannels(imhdr_path=ex.joinpath('corrected.zarr'))

        rgb = params.rgb
        roi = measurement_roi
        rgb_ch, rgb_names = myimage.get_indices_of_bands(rgb)
        rgb_cube = np.array(myimage.get_image_cube(
            rgb_ch, roi=[row_bounds[0], row_bounds[1], col_bounds[0], col_bounds[1]]))

        proj_pd = None
        for k in indices.keys():
            # compute indices
            computed_index = compute_index(indices[k],
                                    row_bounds=row_bounds, col_bounds=col_bounds, imagechannels=myimage)
            computed_index = clean_index_map(computed_index)
        
            indices[k].index_map = computed_index

            proj = compute_index_projection(
                        computed_index, mask,
                        colmin=colmin, colmax=colmax,
                        smooth_window=5)
            indices[k].index_proj = proj

            # create single index plot
            fig, ax = plt.subplots()
            format_dict = asdict(params_plots)
            
            fig, ax1, ax2, ax3 = plot_spectral_profile(
                rgb_image=rgb_cube, mask=mask, index_obj=indices[k],
                format_dict=format_dict, scale=params.scale,
                location=params.location, fig=fig, 
                roi=roi, repeat=True)

            fig.savefig(
                    roi_plot_folder.joinpath(f'{indices[k].index_name}_index_plot.png'),
                dpi=dpi)
            
            # tif maps
            index_map = indices[k].index_map
            contrast = indices[k].index_map_range
            napari_cmap = indices[k].colormap
            export_path = roi_plot_folder.joinpath(f'{indices[k].index_name}_index_map.tif')
            save_tif_cmap(image=index_map, image_path=export_path,
                            napari_cmap=napari_cmap, contrast=contrast)
            
            # export projection to csv
            if proj_pd is None:
                proj_pd = pd.DataFrame({'depth': np.arange(0, len(indices[k].index_proj))})
            proj_pd[indices[k].index_name] = indices[k].index_proj
        
        proj_pd[f'depth [{params.scale_units}]'] = proj_pd['depth'] * params.scale
        proj_pd.to_csv(roi_plot_folder.joinpath('index_projection.csv'), index=False)

        # create multi index plot
        plot_multi_spectral_profile(
                rgb_image=rgb_cube, mask=mask,
                index_objs=[indices[k] for k in indices.keys()], 
                format_dict=format_dict, scale=params.scale,
                fig=fig, roi=roi, repeat=True)

        fig.savefig(
                    roi_plot_folder.joinpath('multi_index_plot'),
                dpi=dpi)
        plt.close(fig)

def compute_normalized_index_params(project_list, index_params_file, export_folder):

    indices = load_index_series(index_params_file)

    # gather all projections
    all_proj = []
    roi_ind = 0
    for ex in project_list:
        proj_path = ex.joinpath(f'roi_{roi_ind}').joinpath('index_plots').joinpath('index_projection.csv')
        all_proj.append(pd.read_csv(proj_path))
    all_proj = pd.concat(all_proj, axis=0)

    # compute min max of index projections
    min_vals = all_proj.min()
    max_vals = all_proj.max()

    # update indices with new min max
    for k, ind in indices.items():
        ind.index_map_range = [min_vals[k].item(), max_vals[k].item()]

    export_index_series(index_series=indices, file_path=export_folder.joinpath('normalized_index_settings.yml'))


    