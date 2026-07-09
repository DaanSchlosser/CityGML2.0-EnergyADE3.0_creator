# 0006. Rhino export emits buildings as grouped Breps, context as meshes

## Status

accepted

## Decision

The GML-to-Rhino converter ([tools/gml_to_rhino.py](../../tools/gml_to_rhino.py))
uses two different geometry representations in one `.3dm`, split by whether the
feature is something the user edits or only looks at.

- **Building surfaces** (wall, roof, ground, and the other `Buildings::` layers)
  are emitted as clean planar Breps: one trimmed-plane surface per polygon,
  oriented outward by the polygon's Newell normal. Every building's surfaces are
  put in a single Rhino group, so one click selects the whole building before
  the user drills into its faces. A holed building polygon falls back to a mesh
  (rhino3dm cannot build a trimmed plane with an interior ring), which keeps
  every face rather than dropping the rare holed one.
- **Landcover and vegetation** stay welded triangle meshes, merged per
  (layer, colour) within a member. They are context the user looks at, never
  edits.

The local-origin offset (the floored RD New envelope corner) is written to
`Settings.ModelBasePoint` so the RD New coordinates can be recovered exactly,
in addition to the human-readable note in the application details.

## Considered Options

**Everything as meshes (the first version).** Rejected once the editing workflow
was clear. A triangulated mesh is the least editable thing to hand to Rhino:
coplanar triangle diagonals clutter every wall, and rhino3dm cannot emit mesh
ngons to hide them. Rhino can osnap to mesh vertices and edges, so a mesh is not
unusable, but a trimmed-plane Brep is a real editable surface (push/pull, offset,
clean edges) where the user actually models.

**Everything as Breps or boundary curves.** Rejected on cost. A representative
400 m address tile is about 258k polygons, but roughly 250k of those are tree
crowns and landcover the user never edits; only about 6k (2.4%) are building
surfaces. Emitting the whole scene as per-polygon Breps or curves would multiply
the object count and file size for geometry that is pure context. Restricting the
Brep path to buildings puts editable surfaces exactly where they are used and
nowhere they are not.

## Consequences

- Buildings become one object per polygon rather than one merged mesh per
  building, so the object count rises (about 3.6k to 8k on the reference tile)
  and the file grows (about 7 MB to 27 MB), because a trimmed-plane Brep carries
  a NURBS surface and trim topology where a mesh shares vertices. This is the
  deliberate price of editable building surfaces; the context meshes stay cheap
  to keep the increase bounded.
- The per-building group is the unit of selection. Isolating one building to work
  on it is a single click plus isolate, then explode into faces.
- Reversing the split (going back to all-mesh, or forward to curves) means
  reworking the emit path and any Rhino workflow built on grouped Breps, which is
  why the choice is recorded here rather than left implicit.
- Because the offset lives in `ModelBasePoint`, an edited model can be pushed back
  to RD New without copying a number out of a prose string.
