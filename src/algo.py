import pyvista as pv
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist

from functools import partial
from multiprocessing import Pool, cpu_count

def process_chunk(points_chunk, normals_chunk, tree, sphere_radius, tol):
    """Process a chunk of points in parallel"""
    centers_chunk = points_chunk + normals_chunk * sphere_radius
    # # Optimize: reduce k to 1 + use radius search
    # # We only need nearest neighbor distance
    # dists, _ = tree.query(centers_chunk, k=1, workers=1)  # workers=1 because we're already parallelizing
    # return dists >= (sphere_radius - tol)

    dists, indices = tree.query(centers_chunk, k=2, workers=1)

    accessible_chunk = dists[:, 1] >= (sphere_radius - tol)
    return accessible_chunk

def find_accessible_surface_parallel(mesh_path, sphere_radius, rotate=False, tol=1e-3, n_workers=None):
    """Parallel version using multiprocessing"""
    mesh = pv.read(mesh_path)
    mesh.clean(inplace=True)

    if rotate:
        mesh = mesh.rotate_y(90, inplace=False)
        mesh = mesh.rotate_x(270, inplace=False)

    # mesh.compute_normals(cell_normals=False, point_normals=True, inplace=True)
    mesh = mesh.compute_normals(cell_normals=False, point_normals=True)
    
    points = mesh.points

    if 'Normals' not in mesh.point_data:
        raise KeyError("Normals not found. Make sure compute_normals() was called successfully.")

    normals = mesh['Normals']
    normals = normals / np.linalg.norm(normals, axis=1, keepdims=True)
    
    # Build optimized KDTree
    tree = cKDTree(points, balanced_tree=True, compact_nodes=True)

    centers = points + normals * sphere_radius
    
    # Split into chunks for parallel processing
    n_workers = n_workers or cpu_count()

    indices = np.arange(len(points))
    chunks = np.array_split(indices, n_workers)
    
    # Prepare arguments for parallel processing
    # args = [(points[chunk], normals[chunk], tree, sphere_radius, tol) 
    #         for chunk in chunks]
    args = []
    for chunk in chunks:
        args.append((
            points[chunk],
            normals[chunk],
            tree,
            sphere_radius,
            tol
        ))
    
    # Parallel execution
    with Pool(n_workers) as pool:
        results = pool.starmap(process_chunk, args)
    
    # Combine results
    accessible = np.concatenate(results)
    mesh['accessible'] = accessible.astype(float)
    
    return mesh, centers

def find_accessible_surface(mesh_path, sphere_radius, tol=1e-3):
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
    
    # 5. Query distances: k=2 because the nearest point will be the contact vertex itself
    dists, _ = tree.query(centers, k=2)
    dist_to_other = dists[:, 1]  # Distance to the second closest point
    
    # 6. Mark accessible points
    # Accessible if no OTHER point is within sphere_radius (with tolerance)
    accessible = dist_to_other >= (sphere_radius - tol)
    
    mesh['accessible'] = accessible.astype(float)
    return mesh, centers

if __name__ == "__main__":
    # path = "/home/none/Projects/lightning/45.03М (Ту-22М3)/Молниеопасные зоны. Blender_1/45_65-М.obj"
    path = "/home/none/Projects/light/objects/obt_LG.obj"
    radius = 50000  
    
    # result, centers = find_accessible_surface(path, sphere_radius=radius, render=True)
    result, centers = find_accessible_surface_parallel(path, sphere_radius=radius, render=True)
    
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