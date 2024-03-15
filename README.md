# Metal Hydrides Database (MHDB)

MHDB is a comprehensive suite designed to facilitate thermodynamic calculations and provide shared access to thermodynamic databases related to Metal Hydrides for H2 storage. This project aims to provide a structured and efficient way to explore and manage data about metal hydrides, including the calculation of relevant physical properties such as H2 decomposition temperature, H2 equilibrium vapor pressure, phase diagrams, and more.

![MHDB Schematic](assets/MHDB.png)

## Features

- Instant online setup for thermodynamic calculations using pycalphad.
- Immediate access to the extensive, curated MHDB database.
- User-defined thermodynamic systems integrating both uploaded and built-in data.
- Open-access thermodynamic database, with reference citing tools.
- Open-source code readily available in the repository.


## Getting Started

1. Open the repository in a GitHub Codespace by clicking on the green ‘<> Code’ button and selecting ‘+’. All subsequent steps are assumed to be executed within this interface.
2. Navigate to the 'notebooks' directory and open the Jupyter notebook of your interest.
3. Follow and execute the notebook cells to perform the thermodynamic calculations.
4. To use your own .tdb files, drop them into the 'tdbs' directory. They'll be parsed and added to the database, allowing calculations that integrate both built-in and uploaded data.

## How to Contribute

We highly value contributions from the community. This project is built on the principles of FAIR open-access under MIT license, with all modules and pieces of code readily available in the repository. In addition, if you have your own thermodynamic databases, you are encouraged to contribute by dragging and dropping your .tdb files into the 'tdbs' directory. These files will be parsed and integrated into the communal database, wherein the references of your work will be readily available for anyone interested in the field.

## Technologies Used

- MongoDB: Used for database management.
- pycalphad: Used for thermodynamic calculations.
- GitHub Codespaces: Used for environment setup.