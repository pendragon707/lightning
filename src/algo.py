import pyvista as pv
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist

from functools import partial
from multiprocessing import Pool, cpu_count
import multiprocessing as mp

import time
from functools import wraps

def timeit(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__}: {elapsed:.4f} seconds")
        return result
    return wrapper

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

@timeit
def find_accessible_surface_parallel(mesh_path, sphere_radius, rotation_angles=None, rotation_order="XYZ", tol=1e-3, n_workers=None):
    """Parallel version using multiprocessing"""

    if not rotation_angles:
        rotation_angles = {
            'X': 0,
            'Y': 0,
            'Z': 0
        }

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

@timeit
def find_accessible_surface(mesh_path, sphere_radius, rotation_angles=None, rotation_order="XYZ", tol=1e-3, n_workers=None):
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
    if not rotation_angles:
        rotation_angles = {
            'X': 0,
            'Y': 0,
            'Z': 0
        }

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

# TEST

import open3d as o3d

@timeit
def find_accessible_surface_open3d(mesh_path, sphere_radius):
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    mesh.compute_vertex_normals()
    
    vertices = np.asarray(mesh.vertices)
    normals = np.asarray(mesh.vertex_normals)
    
    # Build KDTree
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(vertices)
    tree = o3d.geometry.KDTreeFlann(pcd)
    
    accessible = np.zeros(len(vertices), dtype=bool)
    
    for i, (vertex, normal) in enumerate(zip(vertices, normals)):
        center = vertex + normal * sphere_radius
        
        # Query nearest neighbors
        [_, idx, dist] = tree.search_knn_vector_3d(center, 2)
        
        # Check if second nearest is beyond radius
        if len(dist) > 1 and dist[1] >= sphere_radius * sphere_radius:
            accessible[i] = True
    
    # Convert back to PyVista if needed
    mesh_pv = pv.wrap(mesh)
    mesh_pv['accessible'] = accessible.astype(float)
    return mesh_pv


if __name__ == "__main__":
    # pass
    path = "/home/none/Projects/light/objects/obt_LG.obj"
    radius = 50000  

    result, centers = find_accessible_surface(path, sphere_radius=radius)
    result, centers = find_accessible_surface_parallel(path, sphere_radius=radius)
    result, centers = find_accessible_surface_open3d(path, sphere_radius=radius)
    
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
    accessible_mesh.save("images/accessible_fragment_open3d.obj")       

    # # Extract accessible fragment
    # accessible_indices = np.where( result['accessible'] > 0.5)[0]
    # accessible_mesh = result.extract_points(accessible_indices, adjacent_cells=True)    
    # accessible_mesh = accessible_mesh.extract_surface(algorithm='dataset_surface')
    
    # # Visualization
    # p = pv.Plotter()
    # p.add_mesh(result, scalars='accessible', cmap='coolwarm', show_edges=False, smooth_shading=True, opacity=0.3, label='Full Mesh')
    # p.add_mesh(accessible_mesh, color='red', show_edges=False, smooth_shading=True, label='Accessible Surface')
    # p.show() 
    
    # # Save result
    # accessible_mesh.save("images/accessible_fragment.obj")    