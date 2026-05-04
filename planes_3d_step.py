import numpy as np
import matplotlib.pyplot as plt
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
from OCC.Core.GCPnts import GCPnts_UniformAbscissa
from OCC.Core.TopoDS import TopoDS_Edge, topods

def load_step(filepath):
    """Load a STEP file and return the root shape."""
    reader = STEPControl_Reader()
    status = reader.ReadFile(filepath)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"❌ Failed to load STEP file: {filepath}")
    reader.TransferRoots()
    return reader.OneShape()

def extract_edge_points(shape, samples_per_edge=80):
    """Extract 3D point arrays from all edges in the model."""
    all_edges = []
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        edge = topods.Edge(exp.Current())
        try:
            curve = BRepAdaptor_Curve(edge)
            # Uniformly sample points along the exact curve
            abscissa = GCPnts_UniformAbscissa(curve, samples_per_edge)
            if abscissa.IsDone() and abscissa.NbPoints() > 1:
                pts = [curve.Value(abscissa.Parameter(i)) for i in range(1, abscissa.NbPoints() + 1)]
                # Convert to numpy array (N, 3)
                all_edges.append(np.array([[p.X(), p.Y(), p.Z()] for p in pts]))
        except Exception:
            pass  # Skip degenerate or unsupported edges
        exp.Next()
    return all_edges

def project_to_2d(edges_3d, view="front"):
    """
    Project 3D edge points to 2D based on standard CAD views.
    Convention: Z is up, right-handed coordinate system.
    """
    projections = []
    for pts in edges_3d:
        if view == "front":
            # Looking along -Y axis → keep X (right) & Z (up)
            x, y = pts[:, 0], pts[:, 2]
        elif view == "side":
            # Looking along -X axis → keep Y (right) & Z (up)
            x, y = pts[:, 1], pts[:, 2]
        elif view == "bottom":
            # Looking along -Z axis → keep X (right) & Y (forward)
            x, y = pts[:, 0], pts[:, 1]
        else:
            raise ValueError("view must be 'front', 'side', or 'bottom'")
        projections.append((x, y))
    return projections

def plot_projections(shape, views=("front", "side", "bottom")):
    edges_3d = extract_edge_points(shape)
    contours_2d = {}
    
    for view in views:
        contours_2d[view] = project_to_2d(edges_3d, view)
        
        plt.figure(figsize=(6, 6))
        for x, y in contours_2d[view]:
            plt.plot(x, y, 'k-', linewidth=0.5)
            
        plt.title(f"{view.capitalize()} View Projection")
        plt.xlabel("X" if view != "side" else "Y")
        plt.ylabel("Z" if view != "bottom" else "Y")
        plt.axis('equal')
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        plt.show()
        
    return contours_2d

if __name__ == "__main__":
    # STEP_PATH = "objects/base.stp" 
    # STEP_PATH = "/home/none/Projects/lightning/stp/Sborka_Zveno.stp"
    STEP_PATH = "objects/flight.step"  
    shape = load_step(STEP_PATH)
    
    # Returns a dict: {'front': [(x,y)...], 'side': [...], 'bottom': [...]}
    contours = plot_projections(shape)
    print(f"✅ Extracted {len(contours['front'])} projected contours per view.")