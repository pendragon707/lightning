import pyvista as pv
import open3d as o3d
import trimesh

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

# -------------------------- pyvista ------------------------------------

def process_chunk(points_chunk, normals_chunk, tree, sphere_radius, tol):
    """Process a chunk of points in parallel"""
    centers_chunk = points_chunk + normals_chunk * sphere_radius
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

# -------------------------- open3d ------------------------------------

def process_chunk_open3d(args):
    """
    Process chunk using vectorized operations for better performance.
    """
    vertices_chunk, normals_chunk, tree, sphere_radius, tol = args
    
    # Vectorized center calculation
    centers_chunk = vertices_chunk + normals_chunk * sphere_radius
    
    # Query all centers at once (vectorized)
    # Query k=2 for each center
    dists, _ = tree.query(centers_chunk, k=2, workers=1)
    
    # Accessible if second nearest is beyond sphere radius
    accessible_chunk = dists[:, 1] >= (sphere_radius * tol)
    
    return accessible_chunk, centers_chunk

def find_accessible_surface_open3d_parallel(mesh_path, sphere_radius, rotation_angles=None, rotation_order="XYZ", n_workers=None, tol=0.99):
    """
    Parallel version with vectorized chunk processing.
    """
    import time
    
    start_time = time.time()
    
    # 1. Load mesh with Open3D
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    
    # 2. Clean and process mesh
    mesh.remove_duplicated_vertices()
    mesh.remove_duplicated_triangles()
    mesh.remove_non_manifold_edges()
    
    # 3. Apply rotations if specified
    if rotation_angles is None:
        rotation_angles = {'X': 0, 'Y': 0, 'Z': 0}
    
    # Create rotation matrix using Open3D
    rotation_matrix = np.eye(3)
    
    # Convert angles to radians
    angles_rad = {
        'X': np.radians(rotation_angles.get('X', 0)),
        'Y': np.radians(rotation_angles.get('Y', 0)),
        'Z': np.radians(rotation_angles.get('Z', 0))
    }

    # Apply rotations in specified order
    for axis in rotation_order:
        if axis == 'X':
            R_x = np.array([
                [1, 0, 0],
                [0, np.cos(angles_rad['X']), -np.sin(angles_rad['X'])],
                [0, np.sin(angles_rad['X']), np.cos(angles_rad['X'])]
            ])
            rotation_matrix = R_x @ rotation_matrix
        elif axis == 'Y':
            R_y = np.array([
                [np.cos(angles_rad['Y']), 0, np.sin(angles_rad['Y'])],
                [0, 1, 0],
                [-np.sin(angles_rad['Y']), 0, np.cos(angles_rad['Y'])]
            ])
            rotation_matrix = R_y @ rotation_matrix
        elif axis == 'Z':
            R_z = np.array([
                [np.cos(angles_rad['Z']), -np.sin(angles_rad['Z']), 0],
                [np.sin(angles_rad['Z']), np.cos(angles_rad['Z']), 0],
                [0, 0, 1]
            ])
            rotation_matrix = R_z @ rotation_matrix
    
    # Apply rotation to mesh
    if not np.allclose(rotation_matrix, np.eye(3)):
        mesh.rotate(rotation_matrix, center=(0, 0, 0))

    # 3. Compute vertex normals
    mesh.compute_vertex_normals()
    
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)
    normals = np.asarray(mesh.vertex_normals)
    
    print(f"Loaded mesh with {len(vertices)} vertices")
    
    # 4. Build KDTree for efficient queries
    tree = cKDTree(vertices, balanced_tree=True, compact_nodes=True)
    
    # 5. Prepare data for parallel processing
    n_workers = n_workers or cpu_count()
    n_workers = min(n_workers, len(vertices))  # Don't use more workers than vertices
    
    indices = np.arange(len(vertices))
    chunks = np.array_split(indices, n_workers)
    
    print(f"Using {n_workers} workers, {len(chunks)} chunks")
    
    # Prepare arguments for each worker
    args_list = []
    for chunk in chunks:
        args_list.append((
            vertices[chunk],
            normals[chunk],
            tree,
            sphere_radius,
            tol
        ))
    
    # 6. Process in parallel
    from multiprocessing import get_context
    ctx = get_context('spawn')
    
    print("Starting parallel processing...")
    with ctx.Pool(n_workers) as pool:
        results = pool.map(process_chunk_open3d, args_list)
    
    # 7. Combine results
    accessible_list = []
    centers_list = []
    for accessible_chunk, centers_chunk in results:
        accessible_list.append(accessible_chunk)
        centers_list.append(centers_chunk)
    
    accessible = np.concatenate(accessible_list)
    centers = np.concatenate(centers_list)
    
    print(f"Processing completed in {time.time() - start_time:.2f} seconds")
    print(f"Accessible vertices: {np.sum(accessible)} / {len(vertices)}")
    
    # 8. Convert to PyVista
    mesh_pv = pv.PolyData()
    mesh_pv.points = vertices
    faces = np.hstack([np.full((len(triangles), 1), 3), triangles])
    mesh_pv.faces = faces.flatten()
    mesh_pv['accessible'] = accessible.astype(float)
    
    return mesh_pv, centers

@timeit
def find_accessible_surface_open3d(mesh_path, sphere_radius, rotation_angles=None, rotation_order="XYZ", n_workers=None):
    """
    Finds accessible surface fragments using Open3D for better accuracy.
    """
    # 1. Load mesh with Open3D
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    
    # 2. Clean and process mesh
    mesh.remove_duplicated_vertices()
    mesh.remove_duplicated_triangles()
    mesh.remove_non_manifold_edges()
    
    # 3. Apply rotations if specified
    if rotation_angles is None:
        rotation_angles = {'X': 0, 'Y': 0, 'Z': 0}
    
    # Create rotation matrix using Open3D
    rotation_matrix = np.eye(3)
    
    # Convert angles to radians
    angles_rad = {
        'X': np.radians(rotation_angles.get('X', 0)),
        'Y': np.radians(rotation_angles.get('Y', 0)),
        'Z': np.radians(rotation_angles.get('Z', 0))
    }

    # Apply rotations in specified order
    for axis in rotation_order:
        if axis == 'X':
            R_x = np.array([
                [1, 0, 0],
                [0, np.cos(angles_rad['X']), -np.sin(angles_rad['X'])],
                [0, np.sin(angles_rad['X']), np.cos(angles_rad['X'])]
            ])
            rotation_matrix = R_x @ rotation_matrix
        elif axis == 'Y':
            R_y = np.array([
                [np.cos(angles_rad['Y']), 0, np.sin(angles_rad['Y'])],
                [0, 1, 0],
                [-np.sin(angles_rad['Y']), 0, np.cos(angles_rad['Y'])]
            ])
            rotation_matrix = R_y @ rotation_matrix
        elif axis == 'Z':
            R_z = np.array([
                [np.cos(angles_rad['Z']), -np.sin(angles_rad['Z']), 0],
                [np.sin(angles_rad['Z']), np.cos(angles_rad['Z']), 0],
                [0, 0, 1]
            ])
            rotation_matrix = R_z @ rotation_matrix
    
    # Apply rotation to mesh
    if not np.allclose(rotation_matrix, np.eye(3)):
        mesh.rotate(rotation_matrix, center=(0, 0, 0))

    # 3. Compute vertex normals
    mesh.compute_vertex_normals()
    
    vertices = np.asarray(mesh.vertices)
    triangles = np.asarray(mesh.triangles)
    
    # 4. Build KDTree for efficient queries
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(vertices)
    tree = o3d.geometry.KDTreeFlann(pcd)
    
    # 5. Check each vertex
    accessible = np.zeros(len(vertices), dtype=bool)
    centers = np.zeros_like(vertices)
    
    for i, vertex in enumerate(vertices):
        # Get normal at this vertex
        normal = np.asarray(mesh.vertex_normals)[i]
        if np.linalg.norm(normal) == 0:
            continue
            
        # Candidate sphere center
        center = vertex + normal * sphere_radius
        centers[i] = center
        
        # Query nearest neighbors
        [_, idx, dist] = tree.search_knn_vector_3d(center, 2)
        
        # Check if second nearest is beyond sphere radius
        if len(dist) > 1 and dist[1] >= sphere_radius * sphere_radius * 0.99:
            accessible[i] = True
    
    # 6. Convert Open3D mesh to PyVista
    # Method 1: Using vertices and faces
    mesh_pv = pv.PolyData()
    mesh_pv.points = vertices
    
    # Open3D triangles are Nx3, PyVista needs Nx4 (with cell size)
    faces = np.hstack([np.full((len(triangles), 1), 3), triangles])
    mesh_pv.faces = faces.flatten()
    
    # Add the accessible data
    mesh_pv['accessible'] = accessible.astype(float)
    
    return mesh_pv, centers

# -------------------------- trimesh ------------------------------------

@timeit
def find_accessible_surface_trimesh(mesh_path, sphere_radius, rotation_angles=None, rotation_order="XYZ"):
    """
    Uses trimesh as intermediate format for better compatibility.
    """
    
    # 1. Load mesh with trimesh
    mesh_trimesh = trimesh.load(mesh_path)

    # 2. Apply rotations if specified
    if rotation_angles is None:
        rotation_angles = {'X': 0, 'Y': 0, 'Z': 0}
    
    # Convert angles to radians
    angles_rad = {
        'X': np.radians(rotation_angles.get('X', 0)),
        'Y': np.radians(rotation_angles.get('Y', 0)),
        'Z': np.radians(rotation_angles.get('Z', 0))
    }
    
    # Create rotation matrices
    rotation_matrix = np.eye(3)
    
    for axis in rotation_order:
        if axis == 'X':
            R_x = np.array([
                [1, 0, 0],
                [0, np.cos(angles_rad['X']), -np.sin(angles_rad['X'])],
                [0, np.sin(angles_rad['X']), np.cos(angles_rad['X'])]
            ])
            rotation_matrix = R_x @ rotation_matrix
        elif axis == 'Y':
            R_y = np.array([
                [np.cos(angles_rad['Y']), 0, np.sin(angles_rad['Y'])],
                [0, 1, 0],
                [-np.sin(angles_rad['Y']), 0, np.cos(angles_rad['Y'])]
            ])
            rotation_matrix = R_y @ rotation_matrix
        elif axis == 'Z':
            R_z = np.array([
                [np.cos(angles_rad['Z']), -np.sin(angles_rad['Z']), 0],
                [np.sin(angles_rad['Z']), np.cos(angles_rad['Z']), 0],
                [0, 0, 1]
            ])
            rotation_matrix = R_z @ rotation_matrix
    
    # Apply rotation to mesh
    if not np.allclose(rotation_matrix, np.eye(3)):
        mesh_trimesh.apply_transform(np.vstack([np.hstack([rotation_matrix, np.zeros((3, 1))]), [0, 0, 0, 1]]))    
    
    # 2. Get vertices and normals
    vertices = mesh_trimesh.vertices
    vertex_normals = mesh_trimesh.vertex_normals
    
    # 3. Build KDTree
    tree = cKDTree(vertices)
    
    # 4. Check accessibility
    accessible = np.zeros(len(vertices), dtype=bool)
    centers = np.zeros_like(vertices)
    
    for i, (vertex, normal) in enumerate(zip(vertices, vertex_normals)):
        if np.linalg.norm(normal) == 0:
            continue
            
        center = vertex + normal * sphere_radius
        centers[i] = center
        
        # Query nearest neighbors (k=2 because nearest is the vertex itself)
        dists, _ = tree.query(center, k=2)
        if len(dists) > 1 and dists[1] >= sphere_radius * 0.99:
            accessible[i] = True
    
    # 5. Convert to PyVista
    # Trimesh -> PyVista conversion
    mesh_pv = pv.wrap(mesh_trimesh)  # This should work!
    mesh_pv['accessible'] = accessible.astype(float)
    
    return mesh_pv, centers

def process_chunk_trimesh(args):
    """
    Process a chunk of vertices for trimesh algorithm.
    Args is a tuple containing all needed data.
    """
    # Unpack the tuple - it should contain exactly 5 elements
    vertices_chunk, normals_chunk, tree, sphere_radius, tol = args
    
    # Vectorized center calculation
    centers_chunk = vertices_chunk + normals_chunk * sphere_radius
    
    # Query KDTree for all centers in chunk
    dists, _ = tree.query(centers_chunk, k=2, workers=1)
    
    # Check if second nearest is beyond sphere radius
    if len(dists.shape) == 1:
        # Only one point in chunk
        accessible_chunk = np.array([dists[1] >= sphere_radius * tol]) if len(dists) > 1 else np.array([False])
    else:
        accessible_chunk = dists[:, 1] >= (sphere_radius * tol)
    
    return accessible_chunk, centers_chunk

def find_accessible_surface_trimesh_parallel(mesh_path, sphere_radius, rotation_angles=None, rotation_order="XYZ", n_workers=None, tol=0.99, verbose=True):
    """
    Parallel version using trimesh with multiprocessing.
    """
    start_time = time.time()
    
    # 1. Load mesh with trimesh
    if verbose:
        print(f"Loading mesh from: {mesh_path}")
    mesh_trimesh = trimesh.load(mesh_path)

    # 2. Apply rotations if specified
    if rotation_angles is None:
        rotation_angles = {'X': 0, 'Y': 0, 'Z': 0}
    
    # Convert angles to radians
    angles_rad = {
        'X': np.radians(rotation_angles.get('X', 0)),
        'Y': np.radians(rotation_angles.get('Y', 0)),
        'Z': np.radians(rotation_angles.get('Z', 0))
    }
    
    # Create rotation matrices
    rotation_matrix = np.eye(3)
    
    for axis in rotation_order:
        if axis == 'X':
            R_x = np.array([
                [1, 0, 0],
                [0, np.cos(angles_rad['X']), -np.sin(angles_rad['X'])],
                [0, np.sin(angles_rad['X']), np.cos(angles_rad['X'])]
            ])
            rotation_matrix = R_x @ rotation_matrix
        elif axis == 'Y':
            R_y = np.array([
                [np.cos(angles_rad['Y']), 0, np.sin(angles_rad['Y'])],
                [0, 1, 0],
                [-np.sin(angles_rad['Y']), 0, np.cos(angles_rad['Y'])]
            ])
            rotation_matrix = R_y @ rotation_matrix
        elif axis == 'Z':
            R_z = np.array([
                [np.cos(angles_rad['Z']), -np.sin(angles_rad['Z']), 0],
                [np.sin(angles_rad['Z']), np.cos(angles_rad['Z']), 0],
                [0, 0, 1]
            ])
            rotation_matrix = R_z @ rotation_matrix
    
    # Apply rotation to mesh
    if not np.allclose(rotation_matrix, np.eye(3)):
        mesh_trimesh.apply_transform(np.vstack([np.hstack([rotation_matrix, np.zeros((3, 1))]), [0, 0, 0, 1]]))    
    
    # 2. Get vertices and normals
    vertices = np.asarray(mesh_trimesh.vertices)
    vertex_normals = np.asarray(mesh_trimesh.vertex_normals)
    
    if verbose:
        print(f"Loaded mesh with {len(vertices)} vertices")
        print(f"Mesh has {len(mesh_trimesh.faces)} faces")
    
    # 3. Build KDTree
    tree = cKDTree(vertices, balanced_tree=True, compact_nodes=True)
    
    # 4. Prepare data for parallel processing
    n_workers = n_workers or cpu_count()
    n_workers = min(n_workers, len(vertices))  # Don't use more workers than vertices
    
    # Split indices into chunks
    indices = np.arange(len(vertices))
    chunk_indices_list = np.array_split(indices, n_workers)
    
    if verbose:
        print(f"Using {n_workers} workers, {len(chunk_indices_list)} chunks")
    
    # Prepare arguments for each worker - each is a tuple of (vertices_chunk, normals_chunk, tree, sphere_radius, tol)
    args_list = []
    for chunk_indices in chunk_indices_list:
        vertices_chunk = vertices[chunk_indices]
        normals_chunk = vertex_normals[chunk_indices]
        args_list.append((vertices_chunk, normals_chunk, tree, sphere_radius, tol))
    
    # 5. Process in parallel
    if verbose:
        print("Starting parallel processing...")
    
    # Use 'spawn' context for better compatibility
    ctx = mp.get_context('spawn')
    
    with ctx.Pool(n_workers) as pool:
        results = pool.map(process_chunk_trimesh, args_list)
    
    # 6. Combine results
    accessible_list = []
    centers_list = []
    for accessible_chunk, centers_chunk in results:
        accessible_list.append(accessible_chunk)
        centers_list.append(centers_chunk)
    
    accessible = np.concatenate(accessible_list)
    centers = np.concatenate(centers_list)
    
    if verbose:
        elapsed_time = time.time() - start_time
        accessible_count = np.sum(accessible)
        print(f"Processing completed in {elapsed_time:.2f} seconds")
        print(f"Accessible vertices: {accessible_count} / {len(vertices)} ({100*accessible_count/len(vertices):.1f}%)")
    
    # 7. Convert to PyVista
    mesh_pv = pv.wrap(mesh_trimesh)
    mesh_pv['accessible'] = accessible.astype(float)
    
    return mesh_pv, centers

class AlgorithmFactory:
    """Factory for creating algorithm functions"""
    
    _algorithms = {
        'pyvista': {
            'serial': find_accessible_surface,
            'parallel': find_accessible_surface_parallel,
        },
        'open3d': {
            'serial': find_accessible_surface_open3d,
            'parallel': find_accessible_surface_open3d_parallel,
        },
        'trimesh': {
            'serial': find_accessible_surface_trimesh,
            'parallel': find_accessible_surface_trimesh_parallel,
        }
    }
    
    @classmethod
    def get_algorithm(cls, algo_name, use_parallel=False):
        """Get the appropriate algorithm function"""
        algo_config = cls._algorithms.get(algo_name)
        if not algo_config:
            raise ValueError(f"Unknown algorithm: {algo_name}")
        
        mode = 'parallel' if use_parallel else 'serial'
        algo_func = algo_config.get(mode)
        
        if not algo_func:
            raise ValueError(f"Algorithm {algo_name} does not support {mode} mode")
        
        return algo_func
    
    @classmethod
    def get_available_algorithms(cls):
        """Get list of available algorithm names (without _paral suffix)"""
        return list(cls._algorithms.keys())
    
    @classmethod
    def supports_parallel(cls, algo_name):
        """Check if algorithm supports parallel mode"""
        algo_config = cls._algorithms.get(algo_name)
        return algo_config and 'parallel' in algo_config

if __name__ == "__main__":
    pass