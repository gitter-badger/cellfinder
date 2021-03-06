import os
import pytest

import numpy as np

from tifffile import tifffile
from brainio import brainio

from cellfinder.cells.cells import Cell
import cellfinder.extract.extract_cubes as extract_cubes
import cellfinder.tools.tools as tools
import cellfinder.tools.system as system

data_dir = os.path.join("tests", "data")

signal_data_dir = [os.path.join(data_dir, "signal")]
background_data_dir = [os.path.join(data_dir, "background")]
xml_path = os.path.join(data_dir, "cube_extract", "cells.xml")
validate_cubes_dir = os.path.join(data_dir, "cube_extract", "cubes")
validate_cubes_scale_dir = os.path.join(
    data_dir, "cube_extract", "cubes_scale"
)


class CubeExtractArgs:
    def __init__(self, tmpdir):
        self.cells_file_path = xml_path
        self.all_planes_paths = self.get_plane_paths()

        self.signal_ch_ids = [0]
        self.background_ch_id = 1
        self.signal_channel = 0
        self.background_channel = 1

        self.cube_width = 50
        self.cube_height = 50
        self.cube_depth = 20
        self.save_empty_cubes = False

        self.x_pixel_um = 1
        self.y_pixel_um = 1
        self.z_pixel_um = 5

        # get these from parser defaults
        self.x_pixel_um_network = 1
        self.y_pixel_um_network = 1
        self.z_pixel_um_network = 5

        self.n_free_cpus = 0
        self.n_max_threads = 10
        self.max_ram = None

        self.cube_extract_cli = True

        self.paths = Paths(cells_file_path=xml_path, cubes_output_dir=tmpdir)

    @staticmethod
    def get_plane_paths():
        return signal_data_dir + background_data_dir


class Paths:
    def __init__(self, cells_file_path=None, cubes_output_dir=None):
        self.cells_file_path = cells_file_path
        self.tmp__cubes_output_dir = cubes_output_dir


def load_cubes_in_dir(directory):
    cube_list = os.listdir(directory)
    cubes = []
    for file in cube_list:
        file_path = os.path.join(directory, file)
        cubes.append(brainio.load_any(file_path))
    return cubes


def test_cube_extraction(tmpdir, depth=20):
    tmpdir = str(tmpdir)
    args = CubeExtractArgs(tmpdir)
    extract_cubes.main(args)

    validation_cubes = load_cubes_in_dir(validate_cubes_dir)
    test_cubes = load_cubes_in_dir(tmpdir)

    for idx, test_cube in enumerate(test_cubes):
        assert (validation_cubes[idx] == test_cube).all()

    system.delete_directory_contents(tmpdir)

    # test cube scaling
    args.x_pixel_um = 2
    args.y_pixel_um = 2
    args.z_pixel_um = 7.25

    extract_cubes.main(args)

    validation_cubes_scale = load_cubes_in_dir(validate_cubes_scale_dir)
    test_cubes = load_cubes_in_dir(tmpdir)
    for idx, test_cube in enumerate(test_cubes):
        assert (validation_cubes_scale[idx] == test_cube).all()

    #  test edge of data errors
    cell = Cell("x0y0z10", 2)
    plane_paths = os.listdir(signal_data_dir[0])
    first_plane = tifffile.imread(
        os.path.join(signal_data_dir[0], plane_paths[0])
    )
    stack_shape = first_plane.shape + (depth,)
    stacks = {}
    stacks[0] = np.zeros(stack_shape, dtype=np.uint16)
    stacks[0][:, :, 0] = first_plane

    for plane in range(1, depth):
        im_path = os.path.join(signal_data_dir[0], plane_paths[plane])
        stacks[0][:, :, plane] = tifffile.imread(im_path)

    cube = extract_cubes.Cube(cell, 0, stacks)
    assert (cube.data == 0).all()

    cell = Cell("x2500y2500z10", 2)
    cube = extract_cubes.Cube(cell, 0, stacks)
    assert (cube.data == 0).all()

    # test insufficient z-planes for a specific cube
    stacks[0] = stacks[0][:, :, 1:]
    cube = extract_cubes.Cube(cell, 0, stacks)
    assert (cube.data == 0).all()

    # test insufficient z-planes for any cube to be extracted at all.
    system.delete_directory_contents(tmpdir)
    args.z_pixel_um = 0.1

    with pytest.raises(extract_cubes.StackSizeError):
        extract_cubes.main(args)
