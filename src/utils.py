from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

import numpy as np

def load_step(filepath):
    """Load a STEP file and return the root shape."""
    reader = STEPControl_Reader()
    status = reader.ReadFile(filepath)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"❌ Failed to load STEP file: {filepath}")
    reader.TransferRoots()
    return reader.OneShape()

def get_accessible_mesh(result):
    accessible_indices = np.where( result['accessible'] > 0.5)[0]
    accessible_mesh = result.extract_points(accessible_indices, adjacent_cells=True)    
    accessible_mesh = accessible_mesh.extract_surface(algorithm='dataset_surface')
    return accessible_mesh

def rotate_step_shape(shape, angles, rotation_order, center_point=None):
    """Rotate STEP shape to match PyVista rotation."""
    from OCC.Core.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    
    # Use provided center or default to origin
    if center_point is None:
        center = gp_Pnt(0, 0, 0)
    else:
        center = gp_Pnt(center_point[0], center_point[1], center_point[2])
    
    # Initialize transformations
    final_transform = gp_Trsf()  # Identity by default
    
    for axis in rotation_order:
        angle_rad = angles[axis] * 3.14159 / 180.0
        
        # Translation to origin
        to_origin = gp_Trsf()
        to_origin.SetTranslation(gp_Vec(-center.X(), -center.Y(), -center.Z()))
        
        # Rotation
        rotation = gp_Trsf()
        if axis == 'X':
            rotation.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(1,0,0)), angle_rad)
        elif axis == 'Y':
            rotation.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,1,0)), angle_rad)
        elif axis == 'Z':
            rotation.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,0,1)), angle_rad)
        
        # Translation back
        from_origin = gp_Trsf()
        from_origin.SetTranslation(gp_Vec(center.X(), center.Y(), center.Z()))
        
        # Combine: final_transform = from_origin * rotation * to_origin * final_transform
        # Note: Order of multiplication matters!
        temp = gp_Trsf()
        temp.Multiply(to_origin)
        temp.Multiply(rotation)
        temp.Multiply(from_origin)
        
        # Apply to final transform
        final_transform = temp.Multiplied(final_transform)
    
    # Apply transformation
    transformer = BRepBuilderAPI_Transform(shape, final_transform, True)
    transformer.Build()
    return transformer.Shape()

if __name__ == "__main__":
    pass    