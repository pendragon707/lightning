import pyvista as pv
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist

from functools import partial
from multiprocessing import Pool, cpu_count
import multiprocessing as mp

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

def find_accessible_surface_parallel(mesh_path, sphere_radius, rotation_angles, rotation_order="XYZ", tol=1e-3, n_workers=None):
    """Parallel version using multiprocessing"""
    ctx = mp.get_context('spawn')

    mesh = pv.read(mesh_path)
    mesh.clean(inplace=True)
    mesh.triangulate(inplace=True)

    if not mesh.is_manifold:
        print("Mesh is not manifold - filling holes...")
        mesh.fill_holes(10)  # Try to fill holes
        mesh.clean(inplace=True)   

    for axis in rotation_order:
        if axis == 'X':
            mesh = mesh.rotate_x(rotation_angles['X'], inplace=False)                
        elif axis == 'Y':
            mesh = mesh.rotate_y(rotation_angles['Y'], inplace=False)                
        elif axis == 'Z':
            mesh = mesh.rotate_z(rotation_angles['Z'], inplace=False)       
    
    mesh.compute_normals(cell_normals=False, point_normals=True, consistent_normals=True, auto_orient_normals=True, inplace=True)  
    
    points = mesh.points

    if 'Normals' not in mesh.point_data:
        raise KeyError("Normals not found. Make sure compute_normals() was called successfully.")

    normals = mesh['Normals']
    normals = normals / np.linalg.norm(normals, axis=1, keepdims=True)

    # ✅ Check for NaN/Inf in normals
    if np.any(~np.isfinite(normals)):
        print(f"Found {np.sum(~np.isfinite(normals))} invalid normals")
        # Replace invalid normals with zeros
        normals = np.where(np.isfinite(normals), normals, 0)
        # Or drop invalid points entirely
        valid_mask = np.all(np.isfinite(normals), axis=1)
        points = points[valid_mask]
        normals = normals[valid_mask]
        mesh = mesh.extract_points(valid_mask)
    
    # ✅ Check points as well
    if np.any(~np.isfinite(points)):
        print(f"Found invalid points")
        valid_mask = np.all(np.isfinite(points), axis=1)
        points = points[valid_mask]
        normals = normals[valid_mask]
        mesh = mesh.extract_points(valid_mask)    
    
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
    with ctx.Pool(n_workers) as pool:
        results = pool.starmap(process_chunk, args)
    
    # Combine results
    accessible = np.concatenate(results)
    mesh['accessible'] = accessible.astype(float)
    
    return mesh, centers

def find_accessible_surface(mesh_path, sphere_radius, rotation_angles, rotation_order="XYZ", tol=1e-3, n_workers=None):
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
    mesh.triangulate(inplace=True)
    
    if not mesh.is_manifold:
        print("Mesh is not manifold - filling holes...")
        mesh.fill_holes(10)  # Try to fill holes
        mesh.clean(inplace=True) 

    for axis in rotation_order:
        if axis == 'X':
            mesh = mesh.rotate_x(rotation_angles['X'], inplace=False)                
        elif axis == 'Y':
            mesh = mesh.rotate_y(rotation_angles['Y'], inplace=False)                
        elif axis == 'Z':
            mesh = mesh.rotate_z(rotation_angles['Z'], inplace=False) 

    # 2. Compute point normals (assumes outward orientation for closed meshes)
    mesh.compute_normals(cell_normals=False, point_normals=True, consistent_normals=True, auto_orient_normals=True, inplace=True)  
    
    points = mesh.points
    normals = mesh['Normals']

    normals = normals / np.linalg.norm(normals, axis=1, keepdims=True)

    # ✅ Check for NaN/Inf in normals
    if np.any(~np.isfinite(normals)):
        print(f"Found {np.sum(~np.isfinite(normals))} invalid normals")
        # Replace invalid normals with zeros
        normals = np.where(np.isfinite(normals), normals, 0)
        # Or drop invalid points entirely
        valid_mask = np.all(np.isfinite(normals), axis=1)
        points = points[valid_mask]
        normals = normals[valid_mask]
        mesh = mesh.extract_points(valid_mask)
    
    # ✅ Check points as well
    if np.any(~np.isfinite(points)):
        print(f"Found invalid points")
        valid_mask = np.all(np.isfinite(points), axis=1)
        points = points[valid_mask]
        normals = normals[valid_mask]
        mesh = mesh.extract_points(valid_mask)  

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
    pass