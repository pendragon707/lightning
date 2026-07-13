import pyvista as pv
import numpy as np
from scipy.spatial import cKDTree

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg') 

from pathlib import Path

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
from OCC.Core.GCPnts import GCPnts_UniformAbscissa
from OCC.Core.TopoDS import TopoDS_Edge, topods

def extract_edge_points(shape, samples_per_edge=80):
    """Extract 3D point arrays from all edges in the model."""
    all_edges = []
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        edge = topods.Edge(exp.Current())
        try:
            curve = BRepAdaptor_Curve(edge)
            # Uniformly sample points along the exact curve
            abscissa = GCPnts_UniformAbscissa(curve, samples_per_edge)
            if abscissa.IsDone() and abscissa.NbPoints() > 1:
                pts = [curve.Value(abscissa.Parameter(i)) for i in range(1, abscissa.NbPoints() + 1)]
                # Convert to numpy array (N, 3)
                all_edges.append(np.array([[p.X(), p.Y(), p.Z()] for p in pts]))
        except Exception:
            pass  # Skip degenerate or unsupported edges
        exp.Next()
    return all_edges    

def project_to_2d(edges_3d, view="top"):
    """
    Project 3D edge points to 2D based on standard CAD views.
    Convention: Z is up, right-handed coordinate system.
    """
    projections = []
    for pts in edges_3d:
        if view == "top":
            # Looking along -Y axis → keep X (right) & Z (up)
            x, y = pts[:, 0], pts[:, 2]
        elif view == "front":
            # Looking along -X axis → keep Y (right) & Z (up)
            x, y = pts[:, 1], pts[:, 2]
        elif view == "side":
            # Looking along -Z axis → keep X (right) & Y (forward)
            x, y = pts[:, 0], pts[:, 1]
        elif view == "bottom":
            x, y = pts[:, 0], -pts[:, 2]
        else:
            raise ValueError("view must be 'front', 'side', 'top' or 'bottom'")
        projections.append((x, y))
    return projections        

def plot_projections(shape, views=("front", "side", "top", "bottom")):
    edges_3d = extract_edge_points(shape)
    contours_2d = {}
    
    for view in views:
        contours_2d[view] = project_to_2d(edges_3d, view)
        
        plt.figure(figsize=(6, 6))
        for x, y in contours_2d[view]:
            plt.plot(x, y, 'k-', linewidth=0.5)
            
        plt.title(f"{view.capitalize()} View Projection")
        plt.xlabel("X" if view != "side" else "Y")
        plt.ylabel("Z" if view != "top" else "Y")
        plt.axis('equal')
        plt.grid(False)
        plt.tight_layout()
        plt.show()
        
    return contours_2d

def plot_mesh_with_projections(mesh, shape, views=("front", "side", "top", "bottom"), out_dir=None, contours=False):
    """
    Plot PyVista mesh contours and shape projections on same Matplotlib figure.
    
    Parameters:
    - mesh: pv.PolyData - your mesh
    - shape: your shape object (for edge points extraction)
    - views: tuple of views to plot
    """
    # Extract edge points from shape
    edges_3d = extract_edge_points(shape)
    
    # Create subplots
    fig, axes = plt.subplots(1, 4, figsize=(18, 6))
    view_map = {"front": 0, "side": 1, "top": 2, "bottom": 3}
    
    for view in views:
        ax = axes[view_map[view]]
        
        # 1. Plot shape contours
        if contours:
            contours_2d = project_to_2d(edges_3d, view)
            for x, y in contours_2d:
                ax.plot(x, y, 'k-', linewidth=1.5, alpha=0.7, label='Shape Contour')
            
        # 2. Convert and plot mesh
        mesh_x, mesh_y, x_label, y_label = convert_polydata_to_matplotlib(mesh, view)
        
        # Plot mesh points as scatter
        ax.scatter(mesh_x, mesh_y, c='red', s=1, alpha=0.3, label='Mesh Points')
        
        # Format plot
        ax.set_title(f"{view.capitalize()} View")
        ax.set_aspect('equal')
        ax.axis('off')

    image_path = out_dir / "projections.png"
    fig.savefig(image_path)

    plt.tight_layout()
    plt.show()

### ----------------------------------------------------------------------
### pyvista
### ----------------------------------------------------------------------


def get_2d_mask(mesh, contours = None, images=None, out_dir=None):
    projections = {
        'front': (0, -1, 0),   # looking along Y axis
        'top': (0, 0, 1),      # looking along Z axis  
        'side': (-1, 0, 0)     # looking along X axis
    }

    for name, direction in projections.items():
        # Project points onto plane perpendicular to direction
        points = mesh.points.copy()
        
        # Get the projection plane (normal is the direction)
        normal = np.array(direction)
        points_projected = points - np.outer(np.dot(points, normal), normal)
        
        # Create projected mesh
        projected_mesh = pv.PolyData(points_projected)
        projected_mesh.faces = mesh.faces.copy()
        
        # Save or plot
        # plotter = pv.Plotter(window_size=[800, 800])
        plotter = pv.Plotter(window_size=[800, 800], off_screen=True)

        if images:
            plotter.add_background_image( Path(__file__).resolve().parent / "images" / images[name])

        if contours:
            for i, (x, y) in enumerate(contours[name]):
                points_3d = np.column_stack((x, y, np.zeros_like(x)))
                plotter.add_lines(points_3d, color='black', width=1, label=f'Contour {i}')

        plotter.add_mesh(projected_mesh, color='red', show_edges=False, smooth_shading=True)
        plotter.view_xy() if name == 'top' else plotter.view_xz() if name == 'front' else plotter.view_yz()
        
        image_path = out_dir / f"projection_{name}.png"
        # plotter.show(screenshot=image_path)
        plotter.screenshot(image_path, transparent_background=True)

def convert_polydata_to_matplotlib(mesh, view="top"):
    """
    Convert PyVista PolyData to Matplotlib-compatible 2D projection.
    
    Parameters:
    - mesh: pv.PolyData object
    - view: string, one of "front", "side", "top", "bottom"
    
    Returns:
    - list of arrays for plotting
    """
    points = mesh.points
    
    # Apply projection based on view
    if view == "side":
        # Project to XY plane (looking along Z)
        x, y = points[:, 0], points[:, 1]
        x_label, y_label = "X", "Y"
        
    elif view == "front":
        # Project to YZ plane (looking along X)
        x, y = points[:, 1], points[:, 2]
        x_label, y_label = "Y", "Z"
        
    elif view == "top":
        # Project to XZ plane (looking along Y)
        x, y = points[:, 0], points[:, 2]
        x_label, y_label = "X", "Z"

    elif view == "bottom":
        x, y = points[:, 0], -points[:, 2]
        x_label, y_label = "X", "Z"

    else:
        raise ValueError("view must be 'front', 'side', or 'top'")
    
    return x, y, x_label, y_label

def draw_sphere(mesh_path, sphere_radius, center, mesh_mask = None, out_dir=None, step=0):
    mesh = pv.read(mesh_path)
    mesh.clean(inplace=True)    

    sphere = pv.Sphere(radius=sphere_radius, center=center)

    p = pv.Plotter()
    p.add_mesh(mesh, show_edges=False, smooth_shading=True, opacity=0.3, label='Full Mesh')
    if mesh_mask is not None:
        p.add_mesh(mesh_mask, color='red', show_edges=False, smooth_shading=True, label='Accessible Surface')
    p.add_mesh(sphere, color='blue', show_edges=False, smooth_shading=True, opacity=0.3, label='Sphere')
    
    image_path = out_dir / f"sphere_{sphere_radius}_{step}.png"
    p.show(screenshot=image_path)  

def plot_mesh_mask(mesh, mesh_mask=None, out_dir=None, save=True):    
    p = pv.Plotter()
    p.add_mesh(mesh, show_edges=False, smooth_shading=True, opacity=0.3, label='Full Mesh')
    if mesh_mask is not None:
        p.add_mesh(mesh_mask, color='red', show_edges=False, smooth_shading=True, label='Accessible Surface')

    if save:
        image_path = out_dir / "result.png"
        p.show(screenshot=image_path)  
    else:
        p.show()