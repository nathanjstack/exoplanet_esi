import pyvo
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy import Engine
from sqlalchemy.types import Date
import numpy
from datetime import datetime
import argparse

service = pyvo.dal.TAPService("http://voparis-tap-planeto.obspm.fr/tap") 
sun_teff = 5778

# Constants for unit conversion
JUPITER_TO_EARTH_MASS = 318.0      # 1 M_J ≈ 318 M_earth
JUPITER_TO_EARTH_RADIUS = 11.21    # 1 R_J ≈ 11.21 R_earth

def retrieve_catalogue(engine: Engine):
    '''
    Retrieve the current catalogue using the Catalogue of Exoplanets API 
    that have the values required to calculate ESI, exporting it to an SQLite database.

    Args:
        engine (Engine): an SQLalchemy engine connected to the target SQLite database

    Returns:
        None
    '''

    # Find exoplanets where relevant fields are not null and either mass or radius is not null

    print("Retrieving or updating completely new database...")

    query = f"""SELECT target_name, mass, radius, period, star_mass, star_radius, star_teff, semi_major_axis, modification_date, creation_date
    FROM exoplanet.epn_core
    WHERE target_name IS NOT NULL
        AND (mass IS NOT NULL
        OR RADIUS IS NOT NULL)

        AND period IS NOT NULL
        AND star_mass IS NOT NULL
        AND star_radius IS NOT NULL
        AND star_teff IS NOT NULL
        AND semi_major_axis IS NOT NULL
        AND modification_date IS NOT NULL
        AND creation_date IS NOT NULL
        """

    results = service.search(query)
    table = results.to_table()
    df = table.to_pandas()
    
    first_planet = df.iloc[0]["target_name"]
    print(f"Successfully retrieved database with {first_planet} and {len(df)} other exoplanets.")

    df.to_sql("source_data", 
            index=False, 
            con=engine, 
            if_exists="replace", 
            dtype={"planet_updated": Date}
            )
    
    print(f"Database stored in {engine.url}")

def update_catalogue(engine: Engine):
    '''
    Update the current catalogue by calling the Catalogue of Exoplanets API to 
    check if the modification date of exoplanets are more recent than what is in
    the local database, or if there have been any new exoplanets added.

    Args:
        engine (Engine): an SQLalchemy engine connected to the target SQLite database

    Returns:
        None
    '''
    dates = pd.read_sql(
        "SELECT MAX(modification_date) AS last_mod, "
        "MAX(creation_date) AS last_new "
        "FROM source_data;",
        con=engine
    )

    last_mod = dates["last_mod"].iloc[0]
    last_new = dates["last_new"].iloc[0]

    print("Checking for any updates or new entries...")

    query = f"""SELECT target_name, mass, radius, period, star_mass, star_radius, star_teff, semi_major_axis, modification_date, creation_date
    FROM exoplanet.epn_core
    WHERE (modification_date > '{last_mod}'
        OR creation_date > '{last_new}')

        AND (mass IS NOT NULL
        OR RADIUS IS NOT NULL)

        AND period IS NOT NULL
        AND star_mass IS NOT NULL
        AND star_radius IS NOT NULL
        AND star_teff IS NOT NULL
        AND semi_major_axis IS NOT NULL
        AND discovered IS NOT NULL"""

    results = service.search(query)
    table = results.to_table()
    updates_df = table.to_pandas()

    if len(updates_df) > 0:
        print(f"Added or updated {len(updates_df)} exoplanet entries.")
    else:
        print("No updates found.")

    updates_df.to_sql(
    "source_data",
    con=engine,
    if_exists="append",
    index=False
    )

    print(f"Updates stored in {engine.url}")

    # Delete old duplicate entries of exoplanets where a new modified version is introduced
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            DELETE FROM source_data
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM source_data
                GROUP BY target_name
            );
        """)

def fill_esi(engine: Engine, ):
    '''
    Create a new table in the target database and calculate and store 
    the ESI for each relevant exoplanet using the two parameter formula,
    approximating radius if neccesary.

    Args:
        engine (Engine): an SQLalchemy engine connected to the target SQLite database

    Returns:
        None
    '''
    df = pd.read_sql(
    "SELECT * FROM source_data",
    con=engine
    )

    # store whether radius is in the exoplanets fields or not
    df["radius_estimated"] = df["radius"].isna()

    def calculate_esi(row):
        star_radius = row['star_radius']            # in solar radii
        star_teff = row['star_teff']                # in Kelvin
        semi_major_axis = row['semi_major_axis']    # in AU
        planetary_radius = row['radius'] * JUPITER_TO_EARTH_RADIUS
        planetary_mass = row['mass'] * JUPITER_TO_EARTH_MASS

        # estimate radius with mass
        if pd.isna(planetary_radius):
            planetary_radius = planetary_mass ** (1/3)

        luminosity = (star_radius ** 2) * ((star_teff / sun_teff) **4 )
        stellar_flux = (luminosity / (semi_major_axis) ** 2)
        flux_diff = ((stellar_flux - 1) / (stellar_flux + 1)) ** 2
        radius_diff = ((planetary_radius - 1) / (planetary_radius + 1)) ** 2
        esi = 1 - numpy.sqrt((flux_diff + radius_diff) / 2)
        return esi

    print("Calculating Earth Similarity Index (ESI) for each exoplanet...")
    df["esi"] = df.apply(calculate_esi, axis=1)

    # store date calculated 
    df["calculated_on"] = datetime.now()

    # should make 'exoplanet_esis' table name based on user input in future
    df[["target_name", "esi", "creation_date", "calculated_on", "radius_estimated"]].to_sql("exoplanet_esis", index=False, con=engine, if_exists="replace", dtype={"planet_updated": Date})
    print(f"ESIs successfully calculated and outputted in the 'exoplanet_esis' table of {engine.url}")

def main():
    parser = argparse.ArgumentParser(description="Exoplanet catalogue utility")
    parser.add_argument("-d", "--db", type=str, default="exoplanet_catalogue.db", help="SQLite database filename")
    parser.add_argument("-r", "--retrieve", action="store_true", help="Retrieve full catalogue the Catalogue of Exoplanets")
    parser.add_argument("-u", "--update", action="store_true", help="Update catalogue with new or modified exoplanet entries")
    parser.add_argument("-e", "--esi", action="store_true", help="Calculate ESI for all entries and create new table")
    parser.add_argument("-t", "--table", action="store_true", help="Specify table name for ESI calculations")
    
    args = parser.parse_args()
    
    engine = create_engine(f"sqlite:///{args.db}")

    if args.retrieve:
        retrieve_catalogue(engine)
    if args.update:
        update_catalogue(engine)
    if args.esi:
        fill_esi(engine)

if __name__ == "__main__":
    main()