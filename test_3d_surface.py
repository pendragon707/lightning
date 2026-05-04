
import pyvista as pv
import numpy as np
from scipy.spatial import cKDTree

import matplotlib.pyplot as plt

from pathlib import Path

images = {
    'front': "orthographic_front.png",   # looking along Y axis
    'top': "orthographic_front.png",      # looking along Z axis  
    'side': "orthographic_front.png"     # looking along X axis
}

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

def get_2d_mask(mesh, images=None):
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

        plotter.add_mesh(projected_mesh, color='red', show_edges=False, smooth_shading=True)
        plotter.view_xy() if name == 'top' else plotter.view_xz() if name == 'front' else plotter.view_yz()
        plotter.show(screenshot=f'images/projection_{name}.png')

def draw_sphere(mesh, sphere_radius, center, mesh_mask = None):
    sphere = pv.Sphere(radius=sphere_radius, center=center)

    p = pv.Plotter()
    p.add_mesh(mesh, show_edges=False, smooth_shading=True, opacity=0.3, label='Full Mesh')
    if mesh_mask is not None:
        p.add_mesh(mesh_mask, color='red', show_edges=False, smooth_shading=True, label='Accessible Surface')
    p.add_mesh(sphere, color='blue', show_edges=False, smooth_shading=True, opacity=0.3, label='Sphere')
    p.show() 


if __name__ == "__main__":
    # path = "/home/none/Projects/lightning/45.03М (Ту-22М3)/Молниеопасные зоны. Blender_1/45_65-М.obj"
    # path = "objects/flight.obj"

    path = "/home/none/Projects/lightning/new/obj/Sborka_Zveno.obj"

    radius = 342000  
    
    result, centers = find_accessible_surface(path, sphere_radius=radius, render=True)
    # print(result)
    # print( np.unique( result['accessible'] ) )    
    
    # Extract accessible fragment
    accessible_indices = np.where( result['accessible'] > 0.5)[0]
    accessible_mesh = result.extract_points(accessible_indices, adjacent_cells=True)    
    accessible_mesh = accessible_mesh.extract_surface(algorithm='dataset_surface')

    get_2d_mask(accessible_mesh)
    
    # Visualization
    p = pv.Plotter()
    p.add_mesh(result, scalars='accessible', cmap='coolwarm', show_edges=False, smooth_shading=True, opacity=0.3, label='Full Mesh')
    p.add_mesh(accessible_mesh, color='red', show_edges=False, smooth_shading=True, label='Accessible Surface')
    p.show() 
    
    # Save result
    accessible_mesh.save("images/accessible_fragment.obj")