import open3d as o3d
import numpy as np
from scipy.spatial import cKDTree

def find_accessible_surface_open3d(mesh_path, sphere_radius, tol=1e-3):
    """Use Open3D which has better parallelization than PyVista"""
    
    # Load mesh with Open3D
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    mesh.compute_vertex_normals()
    
    # Convert to numpy arrays
    points = np.asarray(mesh.vertices)
    normals = np.asarray(mesh.vertex_normals)
    
    # Build KDTree with optimized parameters
    tree = cKDTree(points, balanced_tree=True, leafsize=16)
    
    # Process in chunks with vectorized operations
    chunk_size = 10000
    n_points = len(points)
    accessible = np.zeros(n_points, dtype=bool)
    
    for i in range(0, n_points, chunk_size):
        end = min(i + chunk_size, n_points)
        chunk_points = points[i:end]
        chunk_normals = normals[i:end]
        
        # Compute centers
        centers = chunk_points + chunk_normals * sphere_radius
        
        # Find distances to second nearest neighbor
        # Use radius search for efficiency
        dists, indices = tree.query(centers, k=min(5, n_points))
        
        if len(dists.shape) == 1:
            dist_to_other = dists
        else:
            dist_to_other = dists[:, 1] if dists.shape[1] > 1 else dists[:, 0]
        
        accessible[i:end] = dist_to_other >= (sphere_radius - tol)
    
    # Convert back to Open3D mesh
    accessible_mesh = mesh.select_by_index(np.where(accessible)[0])
    
    return mesh, accessible_mesh

# Visualization with Open3D
def visualize_open3d(original_mesh, accessible_mesh):
    """Visualize using Open3D's built-in viewer"""
    # Color the original mesh
    original_mesh.paint_uniform_color([0.7, 0.7, 0.7])
    
    # Color accessible parts red
    accessible_mesh.paint_uniform_color([1.0, 0.0, 0.0])
    
    # Visualize
    o3d.visualization.draw_geometries([original_mesh, accessible_mesh])

if __name__ == "__main__":
    path = "/home/none/Projects/lightning/45.03М (Ту-22М3)/Молниеопасные зоны. Blender_1/45_65-М.obj"
    radius = 50000  
    
    result, centers = find_accessible_surface(path, sphere_radius=radius, render=True)
    
    # Extract accessible fragment
    accessible_indices = np.where( result['accessible'] > 0.5)[0]
    accessible_mesh = result.extract_points(accessible_indices, adjacent_cells=True)    
    accessible_mesh = accessible_mesh.extract_surface(algorithm='dataset_surface')

    original_mesh = o3d.io.read_triangle_mesh(path)
    original_mesh.compute_vertex_normals()
    visualize_open3d(original_mesh, accessible_mesh)
    
    # Save result
    accessible_mesh.save("images/accessible_fragment.obj")    