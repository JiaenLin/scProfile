"""scProfile — comprehensive profiling of an annotated single-cell or single-nucleus dataset.

    scprofile doctor                 what is installed, what is missing, and the exact fix
    scprofile install <kernel>       build that kernel's environment from its lock
    scprofile fetch <kernel>         download and verify the references it declares
    scprofile run --kernel a,b,c     run kernels, merge cell-level results, write the report
    scprofile run --all              every installed kernel, in prerequisite order

A HOST FOR KERNELS, not an analysis. The host knows about manifests, environments, provenance and
reports. It knows nothing about velocity, regulons or ligand-receptor pairs - each of those lives
in its own directory, in its own environment, behind a JSON contract.
"""
__version__ = "0.1.0"
