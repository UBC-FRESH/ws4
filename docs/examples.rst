**********************
Examples
**********************

Runnable notebooks, rendered with their output. Each one is a complete, self-contained session that
you can read here or run yourself; they are the fastest way to see WS4 behave before you point it at
your own estate.

These outputs are checked, not trusted:
``python scripts/check_notebooks.py`` re-runs every notebook and reports any whose committed output
has drifted from what the code produces. When it flags one, ``--refresh`` re-runs and rewrites it.

WS4 is two ways in, and the examples use both. Each notebook says which it is in its first paragraph:
the **command-line** sessions run `ws4` and read the files it writes, the **library** sessions import
the API and keep results in frames. `070_library_path` is the library path end to end, the counterpart
to `010_quickstart`'s commands.

The notebooks live in the repository's ``examples/`` directory. To run one, start Jupyter in a clone
of the repository (``python -m jupyter lab examples``) so that the relative paths in the cells
resolve.

.. nbgallery::
   :caption: Examples

   examples/000_environment_check
   examples/010_quickstart
   examples/020_even_flow
   examples/030_sample_estate
   examples/040_patch_targets
   examples/050_routes_and_mills
   examples/060_parameter_sweep
   examples/070_library_path
