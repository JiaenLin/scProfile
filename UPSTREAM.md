
## CellChat — which route each figure takes, measured 2026-08-30

Step zero of the `plugin-figures` skill: name the function the wrapped tool would use, establish
whether it is REACHABLE by running something, and choose the route deliberately. That was never
done for this plugin, so the route was chosen by what happened to be importable in Python.

**Measured on the cluster, in the plugin's own environment** (`Rscript -e 'exists(...)'`,
CellChat 2.2.0.9001): **19 of 20** functions resolve — `computeCommunProbPathway`,
`netAnalysis_computeCentrality`, `identifyCommunicationPatterns`, `rankNet`, `netVisual_circle`,
`netVisual_chord_gene`, `netVisual_heatmap`, `netVisual_bubble`,
`netAnalysis_signalingRole_scatter`, `netAnalysis_signalingRole_heatmap`, `netVisual_aggregate`,
`netVisual_diffInteraction`, `computeNetSimilarity`, `netEmbedding`, `netClustering`,
`netVisual_embedding`, `subsetCommunication`, `mergeCellChat`, `compareInteractions`. Only
`netVisual_river` does not. **Nothing was unavailable; nobody had asked.**

### The statistics are now the tool's own

The R script computed the edge table and stopped; every downstream quantity was re-derived in
Python — pathway probability, centrality, ranked flow, network similarity — each a faithful
transcription and each a **second implementation of a statistic CellChat already computes**. When
two implementations disagree, nothing on the page says which was read.

The script now calls `computeCommunProbPathway`, `netAnalysis_computeCentrality`, `rankNet` and
`computeNetSimilarity`/`netEmbedding` and writes each result beside the edge table. Each call is
guarded so one failing quantity costs its own table rather than the instance.

### The plots are still reimplementations, and that is now a declared departure

Every panel is drawn in Python rather than by `netVisual_*`. Two reasons, and they are different:

- **Deliberate, and to be kept:** the reimplementations correct real defects in the upstream
  encoding — a shared edge scale across a grid, absence split into its two causes, a named cut,
  quantitative size and width keys. `netVisual_circle` has none of those.
- **Not yet decided:** whether the corrected encoding is worth a second implementation for every
  kind, or whether some panels should be native with the caveat stated in the caption.

That decision is per figure and is not made here. What has changed is that it is now a **declared
departure with the defect named**, rather than an accident of what was importable.
