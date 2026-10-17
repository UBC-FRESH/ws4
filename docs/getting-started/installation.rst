============
Installation
============

Requirements
------------

* **Python 3.11 or newer.**
* A C-free install: the core dependencies are pure Python plus NumPy and Pandas
  (``pydantic``, ``typer``, ``rich``, ``pandas``, ``numpy``, ``pyarrow``, ``pyyaml``), all
  installed for you.
* Nothing else for the command line. The optional extras below add capabilities rather than
  fixing missing basics.

Install from source
-------------------

WS4 is installed from its repository:

.. code-block:: bash

   git clone https://github.com/UBC-FRESH/ws4.git
   cd ws4
   python -m pip install -e .

   ws4 --help

``ws4 --help`` lists one command per step of a study: ``build``, ``ingest``, ``validate``,
``simulate``, ``optimize``, ``watch``, ``calibrate``, and ``report``. Each prints where it wrote
its output.

Optional dependencies
---------------------

.. list-table::
   :header-rows: 1
   :widths: 18 20 62

   * - Extra
     - Install
     - What it adds
   * - ``geo``
     - ``pip install -e ".[geo]"``
     - Reading a **shapefile** fragment inventory. A CSV or Parquet inventory needs nothing
       extra, so skip this unless your fragments are spatial files.
   * - ``opt``
     - ``pip install -e ".[opt]"``
     - The optional numerics and solver stack: ``numba`` (compiled patch-state kernels, which
       have an equivalent pure-Python fallback), ``scipy`` (the ``--mip-bound`` penalty bound,
       which raises a clear error without it), ``networkx``, and ``ray``.

Development and documentation builds need more:

.. code-block:: bash

   python -m pip install -r requirements-dev.txt   # pytest, ruff, mypy, numpydoc, hypothesis
   python -m pip install -r docs/requirements.txt  # Sphinx

Platform notes
--------------

WS4 is developed and measured on Linux, on a many-core host. Nothing in the runtime is
Linux-specific, but only Linux is exercised: treat macOS and Windows as unverified. The one
place a platform shows through is the documentation build, which follows the repository layout
with a symlink (see the repository's ``docs/`` directory); on Windows, clone with symlink
support enabled.

Check the install
-----------------

Three commands, in order, prove that the pieces work:

.. code-block:: bash

   ws4 --help                                                # the command line is installed
   ws4 build --xml examples/synthetic/recipe.xml \
             --fragments examples/synthetic/fragments.csv \
             --out tmp/check/compiled                        # the compiler works
   ws4 validate --dataset tmp/check/compiled                 # the dataset is coherent

.. code-block:: text

   Built dataset → tmp/check/compiled
   Dataset is valid → tmp/check/compiled

If ``build`` complains that a dependency is missing, install the extra it names. If ``validate``
reports problems, it lists the file, the column, and what is wrong with it — the dataset is a
contract, and it is checked on the way in (see :doc:`../reference/compiled-dataset`).

Next
----

Continue with :doc:`quickstart` to run a simulation and a search, or :doc:`architecture` to see
how the parts fit together first.
