import os
import sys
sys.path.append(os.getcwd())

import argparse
from datetime import datetime
from pathlib import Path

from src import find_accessible_surface, load_step, get_accessible_mesh
from src import plot_mesh_with_projections, get_2d_mask, plot_mesh_mask

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Dump out the _payload of iNetX packets as ASCII representations')
    parser.add_argument('--obj',  required=False, default="objects/obt_LG.obj",  help='The input obj file')
    parser.add_argument('--stp',  required=False, default="objects/obt_LG.stp",  help='The input stp file file')
    parser.add_argument('--radius',  required=False, default=50000, type=float, help='The radius of sphere')

    parser.add_argument('--draw',  required=False, action='store_true', default=False,  help='Draw shere while algo')
    parser.add_argument('--plots',  required=False, action='store_true', default=False,  help='Print plots after algo')    
    parser.add_argument('--outdir',  required=False, default=datetime.now().strftime("%Y-%m-%d-%H-%M"), help='Name of output directory. Default is out/date')  

    args = parser.parse_args()  

    out_path = Path(os.getcwd()) / "out" / args.outdir 
    print(out_path)
    if not os.path.exists(out_path):
        os.mkdir(out_path)
    
    result, centers = find_accessible_surface(args.obj, sphere_radius=args.radius, render=args.draw, out_dir=out_path)
    
    accessible_mesh = get_accessible_mesh(result)

    # Save result
    save_path = out_path / "accessible_fragment.obj"
    print(save_path)
    accessible_mesh.save(save_path)

    if args.plots:
        shape = load_step(args.stp)    

        plot_mesh_with_projections(accessible_mesh, shape, out_dir=out_path)
        plot_mesh_mask(result, accessible_mesh, out_dir=out_path) 
        get_2d_mask(accessible_mesh, out_dir=out_path)