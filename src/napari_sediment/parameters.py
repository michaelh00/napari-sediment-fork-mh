from dataclasses import dataclass, field
import dataclasses
from pathlib import Path
import yaml

@dataclass
class Param:
    """
    Class for keeping track of processing parameters.
    
    Paramters
    ---------
    project_path: str
        path where the project is saved
    file_paths: list[str]
        list of paths of files belonging to the project
    channels: dict of str
        channel getting exported as source for each file
    rois: dict of arrays
        flat list of rois for each file
    local_project: bool
        if True, images are saved in local folder
    rgb: bool
        if True, images are assumed to be RGB XYC
    
    """
    project_path: str = None
    file_path: str = None
    white_path: str = None
    dark_path: str = None
    main_roi: list = field(default_factory=list)
    rois: list = field(default_factory=list)

    def save_parameters(self, alternate_path=None):
        """Save parameters as yml file.
        
        Parameters
        ----------
        alternate_path : str or Path, optional
            place where to save the parameters file.
        
        """

        if alternate_path is not None:
            save_path = Path(alternate_path).joinpath("Parameters.yml")
        else:
            save_path = Path(self.project_path).joinpath("Parameters.yml")
    
        with open(save_path, "w") as file:
            dict_to_save = dataclasses.asdict(self)
            for path_name in ['project_path', 'file_path', 'white_path', 'dark_path']:
                if dict_to_save[path_name] is not None:
                    if not isinstance(dict_to_save[path_name], str):
                        dict_to_save[path_name] = dict_to_save[path_name].as_posix()
            
            yaml.dump(dict_to_save, file)