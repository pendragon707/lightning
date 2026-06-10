import pyvista as pv
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist

from functools import partial
from multiprocessing import Pool, cpu_count

from src import draw_sphere

def process_chunk(points_chunk, normals_chunk, tree, sphere_radius, tol):
    """Process a chunk of points in parallel"""
    centers_chunk = points_chunk + normals_chunk * sphere_radius
    # Optimize: reduce k to 1 + use radius search
    # We only need nearest neighbor distance
    dists, _ = tree.query(centers_chunk, k=1, workers=1)  # workers=1 because we're already parallelizing
    return dists >= (sphere_radius - tol)

def find_accessible_surface_parallel(mesh_path, sphere_radius, tol=1e-3, n_workers=None, render = False, out_dir=None):
    """Parallel version using multiprocessing"""
    mesh = pv.read(mesh_path)
    mesh.clean(inplace=True)
    mesh.compute_normals(cell_normals=False, point_normals=True, inplace=True)
    
    points = mesh.points
    normals = mesh['Normals']
    
    # Build optimized KDTree
    tree = cKDTree(points, balanced_tree=True, compact_nodes=True)
    
    # Split into chunks for parallel processing
    n_workers = n_workers or cpu_count()
    chunks = np.array_split(np.arange(len(points)), n_workers)
    
    # Prepare arguments for parallel processing
    args = [(points[chunk], normals[chunk], tree, sphere_radius, tol) 
            for chunk in chunks]
    
    # Parallel execution
    with Pool(n_workers) as pool:
        results = pool.starmap(process_chunk, args)
    
    # Combine results
    accessible = np.concatenate(results)
    mesh['accessible'] = accessible.astype(float)
    
    return mesh

def find_accessible_surface(mesh_path, sphere_radius, tol=1e-3, render = False, out_dir=None):
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
        draw_sphere(mesh, sphere_radius, centers[3], out_dir=out_dir)
    
    # 5. Query distances: k=2 because the nearest point will be the contact vertex itself
    dists, _ = tree.query(centers, k=2)
    dist_to_other = dists[:, 1]  # Distance to the second closest point
    
    # 6. Mark accessible points
    # Accessible if no OTHER point is within sphere_radius (with tolerance)
    accessible = dist_to_other >= (sphere_radius - tol)
    
    mesh['accessible'] = accessible.astype(float)
    return mesh, centers

if __name__ == "__main__":
    path = "/home/none/Projects/lightning/45.03М (Ту-22М3)/Молниеопасные зоны. Blender_1/45_65-М.obj"
    radius = 50000  
    
    result, centers = find_accessible_surface(path, sphere_radius=radius, render=True)
    
    # Extract accessible fragment
    accessible_indices = np.where( result['accessible'] > 0.5)[0]
    accessible_mesh = result.extract_points(accessible_indices, adjacent_cells=True)    
    accessible_mesh = accessible_mesh.extract_surface(algorithm='dataset_surface')
    
    # Visualization
    p = pv.Plotter()
    p.add_mesh(result, scalars='accessible', cmap='coolwarm', show_edges=False, smooth_shading=True, opacity=0.3, label='Full Mesh')
    p.add_mesh(accessible_mesh, color='red', show_edges=False, smooth_shading=True, label='Accessible Surface')
    p.show() 
    
    # Save result
    accessible_mesh.save("images/accessible_fragment.obj")    