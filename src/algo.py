import pyvista as pv
import numpy as np
from scipy.spatial import cKDTree

import matplotlib.pyplot as plt

from src import draw_sphere
# from plots import draw_sphere

def find_accessible_surface(mesh_path, sphere_radius, tol=1e-3, render = False, normals_flag=False, out_dir=None):
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
    
    # 2. Compute point normals (assumes outward orientation for closed meshes)                
    mesh.compute_normals(cell_normals=False, point_normals=True, consistent_normals=True, auto_orient_normals=True, inplace=True)  
    
    points = mesh.points
    normals = mesh['Normals']
    # normals = mesh.point_data['Normals']
    
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

    if render:
        draw_sphere(mesh, sphere_radius, centers, out_dir=out_dir, normals=normals_flag, step=1)
        # draw_sphere(mesh, sphere_radius, centers, out_dir=out_dir, normals=normals_flag, step=3)
        # draw_sphere(mesh, sphere_radius, centers, out_dir=out_dir, normals=normals_flag, step=20)
        # draw_sphere(mesh, sphere_radius, centers, out_dir=out_dir, normals=normals_flag, step=50)
        # draw_sphere(mesh, sphere_radius, centers, out_dir=out_dir, normals=normals_flag, step=100)
    
    # 5. Query distances: k=2 because the nearest point will be the contact vertex itself
    dists, _ = tree.query(centers, k=2)
    dist_to_other = dists[:, 1]  # Distance to the second closest point
    
    # 6. Mark accessible points
    # Accessible if no OTHER point is within sphere_radius (with tolerance)
    accessible = dist_to_other >= (sphere_radius - tol)
    
    mesh['accessible'] = accessible.astype(float)
    return mesh, centers

def create_touching_spheres(mesh_path, sphere_radius, render=True, out_dir=None):
    # Read and clean mesh
    mesh = pv.read(mesh_path)
    mesh.clean(inplace=True)
    mesh.triangulate(inplace=True)
    
    # Try both normal orientations
    mesh.compute_normals(cell_normals=False, point_normals=True, 
                         auto_orient_normals=True, inplace=True)
    
    # Get points and normals
    points = mesh.points
    normals = mesh['Normals']
    
    # Build spatial index
    tree = cKDTree(points)
    
    # Try both directions and keep the one that works
    centers_outward = points + normals * sphere_radius
    centers_inward = points - normals * sphere_radius
    
    # Check which orientation produces correct distances
    def check_touching(centers):
        distances = []
        for center in centers:
            dist, _ = tree.query(center)
            distances.append(dist)
        distances = np.array(distances)
        return np.array(distances), np.mean(np.abs(distances - sphere_radius))
    
    distances_out, error_out = check_touching(centers_outward)
    distances_in, error_in = check_touching(centers_inward)
    
    print(f"Outward orientation error: {error_out}")
    print(f"Inward orientation error: {error_in}")
    
    if error_out < error_in:
        centers = centers_outward
        print("Using outward normals")
    else:
        centers = centers_inward
        print("Using inward normals")
    
    # # Additional check: Only keep spheres that actually touch the surface
    # valid_mask = np.abs(distances - sphere_radius) < 1e-4
    # centers = centers[valid_mask]
    # print(f"Keeping {len(centers)} out of {len(points)} spheres")
    
    if render:
        # Create sphere mesh for visualization
        sphere = pv.Sphere(radius=sphere_radius, center=(0,0,0))
        spheres = pv.PolyData()
        
        for center in centers:
            sphere_shifted = sphere.copy()
            sphere_shifted.points = sphere_shifted.points + center
            spheres = spheres.merge(sphere_shifted)
        
        plotter = pv.Plotter()
        plotter.add_mesh(mesh, color='lightblue', opacity=0.3)
        plotter.add_mesh(spheres, color='red', opacity=0.5)
        plotter.show()
        
        if out_dir:
            plotter.screenshot(f"{out_dir}/spheres.png")
    
    return centers, mesh

if __name__ == "__main__":
    # path = "/home/none/Projects/lightning/45.03М (Ту-22М3)/Молниеопасные зоны. Blender_1/45_65-М.obj"
    path = "/home/none/Projects/light/objects/ТАНТК Ту-142/Zip_Files_Solid_ЭМТТ для передачи Формат _OBJ/Tu-142(Low Poly).obj"
    radius = 5000
    
    result, centers = create_touching_spheres(path, sphere_radius=radius, render=True)
    # result, centers = find_accessible_surface(path, sphere_radius=radius, render=True)
    
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