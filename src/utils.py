# from OCC.Core.STEPControl import STEPControl_Reader
# from OCC.Core.IFSelect import IFSelect_RetDone
# from OCC.Core.TopExp import TopExp_Explorer
# from OCC.Core.TopAbs import TopAbs_EDGE
# from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
# from OCC.Core.GCPnts import GCPnts_UniformAbscissa
# from OCC.Core.TopoDS import TopoDS_Edge, topods

import numpy as np

# def load_step(filepath):
#     """Load a STEP file and return the root shape."""
#     reader = STEPControl_Reader()
#     status = reader.ReadFile(filepath)
#     if status != IFSelect_RetDone:
#         raise RuntimeError(f"❌ Failed to load STEP file: {filepath}")
#     reader.TransferRoots()
#     return reader.OneShape()

def get_accessible_mesh(result):
    accessible_indices = np.where( result['accessible'] > 0.5)[0]
    accessible_mesh = result.extract_points(accessible_indices, adjacent_cells=True)    
    accessible_mesh = accessible_mesh.extract_surface(algorithm='dataset_surface')
    return accessible_mesh