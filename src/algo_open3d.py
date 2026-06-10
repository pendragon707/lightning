# import open3d as o3d
# import numpy as np
# from scipy.spatial import cKDTree

# def find_accessible_surface_open3d(mesh_path, sphere_radius, tol=1e-3, render = False, out_dir=None):
#     """Use Open3D which has better parallelization than PyVista"""
    
#     # Load mesh with Open3D
#     mesh = o3d.io.read_triangle_mesh(mesh_path)
#     mesh.compute_vertex_normals()
    
#     # Convert to numpy arrays
#     points = np.asarray(mesh.vertices)
#     normals = np.asarray(mesh.vertex_normals)
    
#     # Build KDTree with optimized parameters
#     tree = cKDTree(points, balanced_tree=True, leafsize=16)
    
#     # Process in chunks with vectorized operations
#     chunk_size = 10000
#     n_points = len(points)
#     accessible = np.zeros(n_points, dtype=bool)
    
#     for i in range(0, n_points, chunk_size):
#         end = min(i + chunk_size, n_points)
#         chunk_points = points[i:end]
#         chunk_normals = normals[i:end]
        
#         # Compute centers
#         centers = chunk_points + chunk_normals * sphere_radius
        
#         # Find distances to second nearest neighbor
#         # Use radius search for efficiency
#         dists, indices = tree.query(centers, k=min(5, n_points))
        
#         if len(dists.shape) == 1:
#             dist_to_other = dists
#         else:
#             dist_to_other = dists[:, 1] if dists.shape[1] > 1 else dists[:, 0]
        
#         accessible[i:end] = dist_to_other >= (sphere_radius - tol)
    
#     # Convert back to Open3D mesh
#     accessible_mesh = mesh.select_by_index(np.where(accessible)[0])
    
#     return mesh, accessible_mesh

# # Visualization with Open3D
# def visualize_open3d(original_mesh, accessible_mesh):
#     """Visualize using Open3D's built-in viewer"""
#     # Color the original mesh
#     original_mesh.paint_uniform_color([0.7, 0.7, 0.7])
    
#     # Color accessible parts red
#     accessible_mesh.paint_uniform_color([1.0, 0.0, 0.0])
    
#     # Visualize
#     o3d.visualization.draw_geometries([original_mesh, accessible_mesh])

# if __name__ == "__main__":
#     # path = "/home/none/Projects/lightning/45.03М (Ту-22М3)/Молниеопасные зоны. Blender_1/45_65-М.obj"
#     path = "/home/none/Projects/light/objects/obt_LG.obj"
#     radius = 50000  
    
#     result, centers = find_accessible_surface_open3d(path, sphere_radius=radius, render=True)
    
#     # Extract accessible fragment
#     accessible_indices = np.where( result['accessible'] > 0.5)[0]
#     accessible_mesh = result.extract_points(accessible_indices, adjacent_cells=True)    
#     accessible_mesh = accessible_mesh.extract_surface(algorithm='dataset_surface')

#     original_mesh = o3d.io.read_triangle_mesh(path)
#     original_mesh.compute_vertex_normals()
#     visualize_open3d(original_mesh, accessible_mesh)
    
#     # Save result
#     accessible_mesh.save("images/accessible_fragment.obj")    


import open3d as o3d
import numpy as np
from scipy.spatial import cKDTree
import copy

def find_accessible_surface_open3d(mesh_path, sphere_radius, tol=1e-3):
    """
    Find accessible surface fragments using Open3D
    """
    print("Loading mesh...")
    # Load mesh with Open3D
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    
    # Compute normals if not present
    if not mesh.has_vertex_normals():
        print("Computing vertex normals...")
        mesh.compute_vertex_normals()
    
    # Convert to numpy arrays
    points = np.asarray(mesh.vertices)
    normals = np.asarray(mesh.vertex_normals)
    
    print(f"Loaded mesh with {len(points)} vertices and {len(mesh.triangles)} triangles")
    
    # Build KDTree for fast distance queries
    print("Building KDTree...")
    tree = cKDTree(points, balanced_tree=True, leafsize=16)
    
    # Compute sphere centers along normals
    print("Computing sphere centers...")
    centers = points + normals * sphere_radius
    
    # Find distances to nearest neighbors
    print("Querying nearest neighbors...")
    # Query k=2 because the nearest point will be the vertex itself
    dists, indices = tree.query(centers, k=min(2, len(points)))
    
    # Handle case when there's only 1 point
    if len(dists.shape) == 1:
        dist_to_other = dists
    else:
        dist_to_other = dists[:, 1] if dists.shape[1] > 1 else dists[:, 0]
    
    # Mark accessible vertices
    accessible = dist_to_other >= (sphere_radius - tol)
    print(f"Accessible vertices: {np.sum(accessible)} / {len(accessible)}")
    
    # Create selection mask for vertices
    vertex_mask = accessible
    
    # Select faces where all vertices are accessible? Or at least one?
    # For surface accessibility, typically we want faces where at least one vertex is accessible
    triangles = np.asarray(mesh.triangles)
    
    # Method 1: Faces with at least one accessible vertex
    face_mask = np.any(vertex_mask[triangles], axis=1)
    
    # Method 2: Faces with all vertices accessible (more strict)
    # face_mask = np.all(vertex_mask[triangles], axis=1)
    
    # Create new mesh with only accessible faces
    print(f"Creating accessible mesh with {np.sum(face_mask)} faces...")
    
    # Get selected triangles
    selected_triangles = triangles[face_mask]
    
    # Create a new mesh
    accessible_mesh = o3d.geometry.TriangleMesh()
    accessible_mesh.vertices = o3d.utility.Vector3dVector(points)
    accessible_mesh.triangles = o3d.utility.Vector3iVector(selected_triangles)
    
    # Copy vertex colors if they exist
    if mesh.has_vertex_colors():
        accessible_mesh.vertex_colors = mesh.vertex_colors
    
    # Compute normals for the new mesh
    accessible_mesh.compute_vertex_normals()
    
    # Remove duplicate vertices for cleaner mesh
    accessible_mesh = accessible_mesh.remove_duplicated_vertices()
    accessible_mesh = accessible_mesh.remove_unreferenced_vertices()
    
    return mesh, accessible_mesh, accessible


def visualize_open3d(original_mesh, accessible_mesh):
    """Visualize using Open3D's built-in viewer"""
    # Create copies to avoid modifying originals
    orig_copy = copy.deepcopy(original_mesh)
    accessible_copy = copy.deepcopy(accessible_mesh)
    
    # Color the original mesh gray
    orig_copy.paint_uniform_color([0.7, 0.7, 0.7])
    
    # Color accessible parts red
    accessible_copy.paint_uniform_color([1.0, 0.0, 0.0])
    
    # Visualize
    print("Opening visualization window...")
    o3d.visualization.draw_geometries(
        [orig_copy, accessible_copy],
        window_name="Accessible Surface Detection",
        width=1024,
        height=768,
        mesh_show_wireframe=False,
        mesh_show_back_face=False
    )


def save_accessible_mesh(accessible_mesh, output_path):
    """Save accessible mesh to file"""
    o3d.io.write_triangle_mesh(output_path, accessible_mesh)
    print(f"Saved accessible mesh to {output_path}")


# Alternative: Export as OBJ with accessibility information
def export_with_accessibility(original_mesh, accessible_mask, output_path):
    """Export mesh with accessibility as vertex attribute"""
    # Create a copy
    mesh = copy.deepcopy(original_mesh)
    
    # Add accessibility as vertex attribute
    # Open3D doesn't directly support custom vertex attributes in OBJ,
    # but we can use colors to visualize
    colors = np.asarray(mesh.vertex_colors) if mesh.has_vertex_colors() else np.zeros((len(mesh.vertices), 3))
    
    # Set color based on accessibility: red for accessible, gray for inaccessible
    for i in range(len(mesh.vertices)):
        if accessible_mask[i]:
            colors[i] = [1.0, 0.0, 0.0]  # Red for accessible
        else:
            colors[i] = [0.5, 0.5, 0.5]  # Gray for inaccessible
    
    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
    
    # Save as colored OBJ (some viewers support vertex colors in OBJ)
    o3d.io.write_triangle_mesh(output_path, mesh, write_vertex_colors=True)
    print(f"Saved colored mesh to {output_path}")

# Parallel version with chunking for very large meshes
def find_accessible_surface_open3d_parallel(mesh_path, sphere_radius, tol=1e-3, chunk_size=10000):
    """
    Memory-efficient version for very large meshes
    """
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    mesh.compute_vertex_normals()
    
    points = np.asarray(mesh.vertices)
    normals = np.asarray(mesh.vertex_normals)
    
    tree = cKDTree(points)
    n_points = len(points)
    accessible = np.zeros(n_points, dtype=bool)
    
    # Process in chunks to save memory
    for start in range(0, n_points, chunk_size):
        end = min(start + chunk_size, n_points)
        chunk_points = points[start:end]
        chunk_normals = normals[start:end]
        
        # Compute centers for this chunk
        centers = chunk_points + chunk_normals * sphere_radius
        
        # Query distances
        dists, _ = tree.query(centers, k=2)
        
        if len(dists.shape) == 1:
            dist_to_other = dists
        else:
            dist_to_other = dists[:, 1]
        
        accessible[start:end] = dist_to_other >= (sphere_radius - tol)
        
        print(f"Processed {end}/{n_points} vertices")
    
    # Create accessible mesh
    triangles = np.asarray(mesh.triangles)
    face_mask = np.any(accessible[triangles], axis=1)
    selected_triangles = triangles[face_mask]
    
    accessible_mesh = o3d.geometry.TriangleMesh()
    accessible_mesh.vertices = o3d.utility.Vector3dVector(points)
    accessible_mesh.triangles = o3d.utility.Vector3iVector(selected_triangles)
    accessible_mesh.compute_vertex_normals()
    
    return mesh, accessible_mesh, accessible
    

if __name__ == "__main__":
    # Path to your mesh
    path = "/home/none/Projects/lightning/45.03М (Ту-22М3)/Молниеопасные зоны. Blender_1/45_65-М.obj"
    radius = 50000  # Sphere radius in same units as mesh
    
    print("Starting accessible surface detection...")
    print(f"Mesh: {path}")
    print(f"Sphere radius: {radius}")
    
    # Run detection
    original_mesh, accessible_mesh, accessible_vertices = find_accessible_surface_open3d(
        path, 
        sphere_radius=radius,
        tol=1e-3
    )
    
    # Save results
    save_accessible_mesh(accessible_mesh, "accessible_fragment_open3d.obj")
    export_with_accessibility(original_mesh, accessible_vertices, "mesh_with_accessibility.obj")
    
    # Visualize
    visualize_open3d(original_mesh, accessible_mesh)
    
    # Print statistics
    print("\n--- Statistics ---")
    print(f"Total vertices: {len(original_mesh.vertices)}")
    print(f"Total faces: {len(original_mesh.triangles)}")
    print(f"Accessible vertices: {np.sum(accessible_vertices)}")
    print(f"Accessible faces: {len(accessible_mesh.triangles)}")
    print(f"Percentage accessible: {100 * np.sum(accessible_vertices) / len(accessible_vertices):.2f}%")