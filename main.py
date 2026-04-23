# input - flight.obj (for mesh alghorithm), flight.step (for picture)

import pyvista as pv
import numpy as np
from scipy.spatial import cKDTree
import matplotlib.pyplot as plt
from pathlib import Path

from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
from OCC.Core.GCPnts import GCPnts_UniformAbscissa
from OCC.Core.TopoDS import TopoDS_Edge, topods

def load_step(filepath):
    """Load a STEP file and return the root shape."""
    reader = STEPControl_Reader()
    status = reader.ReadFile(filepath)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"❌ Failed to load STEP file: {filepath}")
    reader.TransferRoots()
    return reader.OneShape()

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

def project_to_2d(edges_3d, view="front"):
    """
    Project 3D edge points to 2D based on standard CAD views.
    Convention: Z is up, right-handed coordinate system.
    """
    projections = []
    for pts in edges_3d:
        if view == "front":
            # Looking along -Y axis → keep X (right) & Z (up)
            x, y = pts[:, 0], pts[:, 2]
        elif view == "side":
            # Looking along -X axis → keep Y (right) & Z (up)
            x, y = pts[:, 1], pts[:, 2]
        elif view == "top":
            # Looking along -Z axis → keep X (right) & Y (forward)
            x, y = pts[:, 0], pts[:, 1]
        else:
            raise ValueError("view must be 'front', 'side', or 'top'")
        projections.append((x, y))
    return projections        

def plot_projections(shape, views=("front", "side", "top")):
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


def plot_mesh_with_projections(mesh, shape, views=("front", "side", "top")):
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
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    view_map = {"front": 0, "side": 1, "top": 2}
    
    for view in views:
        ax = axes[view_map[view]]
        
        # 1. Plot shape contours
        contours_2d = project_to_2d(edges_3d, view)
        for x, y in contours_2d:
            ax.plot(x, y, 'k-', linewidth=1.5, alpha=0.7, label='Shape Contour')
        
        # 2. Convert and plot mesh
        mesh_x, mesh_y, x_label, y_label = convert_polydata_to_matplotlib(mesh, view)
        
        # Plot mesh points as scatter
        ax.scatter(mesh_x, mesh_y, c='red', s=1, alpha=0.3, label='Mesh Points')
        
        # Format plot
        ax.set_title(f"{view.capitalize()} View")
        # ax.set_xlabel(x_label)
        # ax.set_ylabel(y_label)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # # Add legend (avoid duplicates)
        # handles, labels = ax.get_legend_handles_labels()
        # by_label = dict(zip(labels, handles))
        # ax.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=8)
        
    plt.tight_layout()
    plt.show()

def find_accessible_surface(mesh_path, sphere_radius, tol=1e-3, render = False):
    """
    Finds surface fragments where a sphere of fixed radius can touch 
    without intersecting or penetrating the mesh elsewhere.
    
    Parameters:
        mesh_path (str): Path to OBJ file
        sphere_radius (float): Radius of the checking sphere
        tol (float): Numerical tolerance for intersection checking
        
    Returns:
        pyvista.PolyData: Mesh with 'accessible' point data array (1.0 or 0.0)
    """
    # 1. Load & clean mesh
    mesh = pv.read(mesh_path)
    mesh.clean(inplace=True)  # Remove duplicate vertices
    
    # 2. Compute point normals (assumes outward orientation for closed meshes)
    mesh.compute_normals(cell_normals=False, point_normals=True, inplace=True)
    
    points = mesh.points
    normals = mesh['Normals']

    # 3. Build spatial index for fast distance queries
    tree = cKDTree(points)
    
    # 4. Candidate sphere centers (r units along the normal)
    centers = points + normals * sphere_radius

    if render:
        draw_sphere(mesh, radius, centers[3])
    
    # 5. Query distances: k=2 because the nearest point will be the contact vertex itself
    dists, _ = tree.query(centers, k=2)
    dist_to_other = dists[:, 1]  # Distance to the second closest point
    
    # 6. Mark accessible points
    # Accessible if no OTHER point is within sphere_radius (with tolerance)
    accessible = dist_to_other >= (sphere_radius - tol)
    
    mesh['accessible'] = accessible.astype(float)
    return mesh, centers

def get_2d_mask(mesh, contours = None, images=None):
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
        plotter = pv.Plotter(window_size=[800, 800])

        if images:
            plotter.add_background_image( Path(__file__).resolve().parent / "images" / images[name])

        if contours:
            for i, (x, y) in enumerate(contours[name]):
                points_3d = np.column_stack((x, y, np.zeros_like(x)))
                plotter.add_lines(points_3d, color='black', width=3, label=f'Contour {i}')

        plotter.add_mesh(projected_mesh, color='red', show_edges=False, smooth_shading=True)
        plotter.view_xy() if name == 'top' else plotter.view_xz() if name == 'front' else plotter.view_yz()
        plotter.show(screenshot=f'images/projection_{name}.png')

def convert_polydata_to_matplotlib(mesh, view="front"):
    """
    Convert PyVista PolyData to Matplotlib-compatible 2D projection.
    
    Parameters:
    - mesh: pv.PolyData object
    - view: string, one of "front", "side", "top"
    
    Returns:
    - list of arrays for plotting
    """
    points = mesh.points
    
    # Apply projection based on view
    if view == "top":
        # Project to XY plane (looking along Z)
        x, y = points[:, 0], points[:, 1]
        x_label, y_label = "X", "Y"
        
    elif view == "side":
        # Project to YZ plane (looking along X)
        x, y = points[:, 1], points[:, 2]
        x_label, y_label = "Y", "Z"
        
    elif view == "front":
        # Project to XZ plane (looking along Y)
        x, y = points[:, 0], points[:, 2]
        x_label, y_label = "X", "Z"
    else:
        raise ValueError("view must be 'front', 'side', or 'top'")
    
    return x, y, x_label, y_label


def draw_sphere(mesh, sphere_radius, center, mesh_mask = None):
    sphere = pv.Sphere(radius=sphere_radius, center=center)

    p = pv.Plotter()
    p.add_mesh(mesh, show_edges=False, smooth_shading=True, opacity=0.3, label='Full Mesh')
    if mesh_mask:
        p.add_mesh(mesh_mask, color='red', show_edges=False, smooth_shading=True, label='Accessible Surface')
    p.add_mesh(sphere, color='blue', show_edges=False, smooth_shading=True, opacity=0.3, label='Sphere')
    p.show() 


if __name__ == "__main__":
    # path = "/home/none/Projects/lightning/45.03М (Ту-22М3)/Молниеопасные зоны. Blender_1/45_65-М.obj"
    # path = "objects/flight.obj"
    # path_step = "objects/base.stp"

    path = "objects/obt_LG.obj"
    path_step = "objects/obt_LG.stp"    

    radius = 50
    
    result, centers = find_accessible_surface(path, sphere_radius=radius, render=False) 
    
    # Extract accessible fragment
    accessible_indices = np.where( result['accessible'] > 0.5)[0]
    accessible_mesh = result.extract_points(accessible_indices, adjacent_cells=True)    
    accessible_mesh = accessible_mesh.extract_surface(algorithm='dataset_surface')

    # Save result
    accessible_mesh.save("images/accessible_fragment.obj")

    print(type(accessible_mesh))

    # draw_sphere(result, radius, centers[3], accessible_mesh)

    shape = load_step(path_step)

    # get_2d_mask(accessible_mesh, contours)

    plot_mesh_with_projections(accessible_mesh, shape)
    
    # Visualization
    p = pv.Plotter()
    p.add_mesh(result, scalars='accessible', cmap='coolwarm', show_edges=False, smooth_shading=True, opacity=0.3, label='Full Mesh')
    p.add_mesh(accessible_mesh, color='red', show_edges=False, smooth_shading=True, label='Accessible Surface')
    p.show() 