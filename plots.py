import os
import sys
sys.path.append(os.getcwd())

import argparse
from pathlib import Path
from datetime import datetime

import pyvista as pv

from src import plot_mesh_with_projections, get_2d_mask, load_step, plot_mesh_mask

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Dump out the _payload of iNetX packets as ASCII representations')
    parser.add_argument('--obj',  required=False, default="objects/base.obj",  help='The input obj file')
    parser.add_argument('--stp',  required=False, default="objects/base.stp",  help='The input stp file file')
    parser.add_argument('--mask',  required=False,  default="/home/none/Projects/light/out/base/accessible_fragment.obj", help='Mask with accessible fragment for plots')
    parser.add_argument('--outdir',  required=False, default=datetime.now().strftime("%Y-%m-%d-%H-%M"), help='Name of output directory. Default is out/date')  
    # потом добавить выбор, а какие графики строить???    

    args = parser.parse_args()  

    out_path = Path(os.getcwd()) / "out" / args.outdir 
    print(out_path)
    if not os.path.exists(out_path):
        os.mkdir(out_path)

    mesh = pv.read(args.obj)
    mesh_mask = pv.read(args.mask)
    shape = load_step(args.stp)        

    plot_mesh_with_projections(mesh_mask, shape, out_dir=out_path)
    plot_mesh_mask(mesh, mesh_mask, out_dir=out_path) 
    get_2d_mask(mesh_mask, out_dir=out_path)