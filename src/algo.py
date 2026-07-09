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
    dists, indices = tree.query(centers_chunk, k=2, workers=1)
    accessible_chunk = dists[:, 1] >= (sphere_radius - tol)
    
    return accessible_chunk

@timeit
def find_accessible_surface_parallel(mesh_path, sphere_radius, rotate_x=0.0, rotate_y=0.0, rotate_z=0.0, tol=1e-3, 
                                     n_workers=None, progress_callback=None):
    """Parallel version using multiprocessing"""
    ctx = mp.get_context('spawn')

    mesh = pv.read(mesh_path)
    mesh.clean(inplace=True)
    mesh.triangulate(inplace=True)

    if not mesh.is_manifold:
        print("Mesh is not manifold - filling holes...")
        mesh.fill_holes(10)  # Try to fill holes
        mesh.clean(inplace=True)     
    
    mesh = mesh.rotate_y(rotate_y, inplace=False)
    mesh = mesh.rotate_x(rotate_x, inplace=False)    
    mesh = mesh.rotate_z(rotate_z, inplace=False)
    
    mesh.compute_normals(cell_normals=False, point_normals=True, consistent_normals=True, auto_orient_normals=True, inplace=True)  
    
    points = mesh.points

    if 'Normals' not in mesh.point_data:
        raise KeyError("Нормали не найдены. Убедитесь, что compute_normals() запустилась успешно.")

    normals = mesh['Normals']
    normals = normals / np.linalg.norm(normals, axis=1, keepdims=True)

    # Check for NaN/Inf in normals
    if np.any(~np.isfinite(normals)):
        print(f"Найдены {np.sum(~np.isfinite(normals))} неправильные нормали")
        # Replace invalid normals with zeros
        normals = np.where(np.isfinite(normals), normals, 0)
        # Or drop invalid points entirely
        valid_mask = np.all(np.isfinite(normals), axis=1)
        points = points[valid_mask]
        normals = normals[valid_mask]
        mesh = mesh.extract_points(valid_mask)
    
    # Check points as well
    if np.any(~np.isfinite(points)):
        print(f"Найдены неправильные точки")
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
    args = []
    for chunk in chunks:
        args.append((
            points[chunk],
            normals[chunk],
            tree,
            sphere_radius,
            tol
        ))

    if progress_callback:
        progress_callback("preprocess", 20, "Модель загружена")

    total_chunks = len(chunks)
    accessible_parts = []                
    
    # Parallel execution
    with ctx.Pool(n_workers) as pool:    
        # results = pool.starmap(process_chunk, args)
        
        for i, result in enumerate(pool.starmap(process_chunk, args)):
            accessible_parts.append(result)
            
            # Calculate progress (30% to 90% for processing chunks)
            progress = 30 + (i + 1) / total_chunks * 60
            if progress_callback:
                progress_callback("processing", progress, f"{i+1}/{total_chunks}")
    
    # Combine results
    # accessible = np.concatenate(results)
    accessible = np.concatenate(accessible_parts)
    mesh['accessible'] = accessible.astype(float)

    if progress_callback:
        progress_callback("complete", 100, "Обработка завершена")
    
    return mesh, centers

@timeit
def find_accessible_surface(mesh_path, sphere_radius, rotate_x=0.0, rotate_y=0.0, rotate_z=0.0, tol=1e-3, n_workers=None):
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

    mesh = mesh.rotate_y(rotate_y, inplace=False)
    mesh = mesh.rotate_x(rotate_x, inplace=False)    
    mesh = mesh.rotate_z(rotate_z, inplace=False)

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


def sample_sphere_surface(center, radius, n_samples=1000):
    """Generate points uniformly on sphere surface using Fibonacci sphere"""
    phi = np.pi * (3 - np.sqrt(5))  # Golden angle
    
    points = np.zeros((n_samples, 3))
    for i in range(n_samples):
        y = 1 - (i / (n_samples - 1)) * 2  # y from 1 to -1
        radius_at_y = np.sqrt(1 - y * y)
        theta = phi * i
        
        points[i] = center + radius * np.array([
            np.cos(theta) * radius_at_y,
            y,
            np.sin(theta) * radius_at_y
        ])
    
    return points

@timeit
def find_accessible_surface_improved(mesh_path, sphere_radius, rotate_x=0.0, rotate_y=0.0, rotate_z=0.0, tol=1e-3, n_workers=None, n_samples=2000):
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

    mesh = mesh.rotate_y(rotate_y, inplace=False)
    mesh = mesh.rotate_x(rotate_x, inplace=False)    
    mesh = mesh.rotate_z(rotate_z, inplace=False)

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
    
    # For each point, sample sphere surface and check intersections
    accessible = np.zeros(len(points), dtype=bool)
    
    for i, (point, normal) in enumerate(zip(points, normals)):
        center = point + normal * sphere_radius
        
        # Sample points on sphere surface
        sphere_points = sample_sphere_surface(center, sphere_radius, n_samples)
        
        # Check if any sphere surface point is inside the mesh
        # Query nearest mesh vertex
        dists, _ = tree.query(sphere_points, k=1)
        
        # If ALL surface points are outside the mesh (dist > eps), it's accessible
        if np.all(dists > 1e-6):  # Small epsilon for numerical stability
            accessible[i] = True
    
    mesh['accessible'] = accessible.astype(float)
    return mesh, centers

if __name__ == "__main__":
    # path = "/home/none/Projects/lightning/45.03М (Ту-22М3)/Молниеопасные зоны. Blender_1/45_65-М.obj"
    path = "/home/none/Projects/light/objects/obt_LG.obj"
    radius = 50000  
    
    # result, centers = find_accessible_surface(path, sphere_radius=radius)
    # result, centers = find_accessible_surface_parallel(path, sphere_radius=radius)
    result, centers = find_accessible_surface_improved(path, sphere_radius=radius)
    
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