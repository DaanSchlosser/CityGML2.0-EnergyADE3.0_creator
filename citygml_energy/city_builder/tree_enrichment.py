# This module is intentionally empty.
#
# Earlier revisions wired in OpenStreetMap ``natural=tree`` nodes and the
# Landelijk Register Monumentale Bomen (via the Bomenstichting's ArcGIS
# FeatureServer) as nearest-neighbour attribute enrichments for CFTree
# reconstructions. That code was removed because the project's
# vegetation pipeline is now scoped to Dutch government open data only,
# and the two government registers that could carry per-tree
# information (BGT ``vegetatieobject``, Top10NL) carry no attributes
# beyond the point location itself. See
# ``docs/vegetation_integration_report.md`` for the full rationale.
#
# The file is kept as a pointer rather than deleted so that a future
# contributor searching the git history for "tree enrichment" lands
# here and sees the "why". Safe to delete outright.
