from pathlib import Path
from typing import Optional

import common
from factorio_sat.network import *
from . import sat_common


def network_create(network_filename: str, size: int):
    if size <= 1:
        raise RuntimeError('Input size too small')

    network = create_benes_network(size)
    save_network(network_filename, network)

def network_render(network: str, output_filename: Optional[str] = None, engine: str = 'dot'):
    if output_filename is not None:
        output_filename_parts = output_filename.split('.')
        if len(output_filename_parts) == 1:
            output_filename = output_filename + '.png'
    else:
        output_filename = "SAT_Network.png"
    output_filename = str(Path(common.output_folder) / output_filename)
    network = sat_common.parse_network_str(network)
    plot(network, output_filename, engine)

def network_parse(network_filename: str, assume_valid_output: bool = False):
    tiles = np.array(json.loads(input()))
    for i, row in enumerate(tiles):
        for j, item in enumerate(row):
            tiles[i, j] = blueprint.read_tile(item)

    network = parse_network(tiles, assume_valid_output)
    network = tidy_network(network)

    save_network(network_filename, network)

def network_flip(in_network: str, out_network_filename: str):
    in_network = sat_common.parse_network_str(in_network)
    out_network = flip_network(in_network)
    out_network = out_network[::-1]
    save_network(out_network_filename, out_network)