## About
This repository is designed to function as an ETL pipeline that extracts confirmed exoplanet data from the [Catalogue of Exoplanets](https://exoplanet.eu/catalog/), filters for those exoplanets that have the required fields, and stores this data in a table in a database, with another table used to contain the calculated Earth Similarity Index (ESI) for each planet, as defined by a simplified two parameter formula from the [Habitable World Catalogue](https://phl.upr.edu/projects/earth-similarity-index-esi):
![ESI](https://latex.codecogs.com/png.latex?ESI(S,R)=1-\sqrt{\frac12[(\frac{S-S_\oplus}{S+S_\oplus})^2+(\frac{R-R_\oplus}{R+R_\oplus})^2]})
where S is stellar flux, R is radius, S⊕ is Earth's solar flux, and R⊕ is Earth's radius. This formula applies to exoplanets detected by different methods where either only mass or only the radius of the planet is known by assuming that:
$$R = M^{1/3}$$
Because this is quite approximate, if an exoplanet requires this relation to be used in the calculation of its ESI, it is marked in the database.

This program currently serves 3 main functions:
1. Retrieving the entire catalogue of exoplanets from the Catalogue of Exoplanets and storing them in an SQLite database
2. Updating an existing catalogue by comparing the dates in which data for each exoplanet was modified and seeing if any new exoplanets have been added, to avoid retrieving the entire catalogue every update.
3. Creating a new table in the database that calculates the ESI for each exoplanet, approximating radius using the above relation if necessary. 
## Installation
For the program to run, `requirements.txt` and `retrieve_catalogue.py` must be installed. `exoplanet_catalogue.db` is optional and not needed if you wish to retrieve a new clean database.

This program was written in `Python 3.11.9`, and to install the necessary packages execute:
```zsh
pip install -r requirements.txt
```
## Running
After installing the relevant packages the program can be run with:
```zsh
python retrieve_catalogue.py --db "database_name.db" --retrieve --esi
```

This will call the Catalogue of Exoplanets API, filter and store the results in the SQLite database `database_name.db` in a table named `source_data`, and calculate the ESI for each planet, storing them in a table named `exoplanet_esis`.
### Flags
* `"-d"`, `"--db"`, SQLite database filename, default is `exoplanet_catalogue.db`, optional
* `"-r"`,` "--retrieve"`, Retrieve full catalogue the Catalogue of Exoplanets, optional
* `"-u"`, `"--update"`, Update catalogue with new or modified exoplanet entries, optional
* `"-e"`, `"--esi"`, Calculate ESI for all entries and create new table, optional