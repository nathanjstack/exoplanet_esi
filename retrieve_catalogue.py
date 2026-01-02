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

engine = create_engine("sqlite:///exoplanet_catalogue.db")

def retrieve_catalogue(engine: Engine):
    '''
    Retrieve the current catalogue using the Catalogue of Exoplanets API 
    that have the values required to calculate ESI, exporting it to an SQLite database.
    '''
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

    df.to_sql("source_data", 
            index=False, 
            con=engine, 
            if_exists="replace", 
            dtype={"planet_updated": Date}
            )

def update_catalogue(engine: Engine): # needs to accept a db 
    '''
    Update the 
    '''
    # Update any exoplanets if new data is found
        # Read only the two columns needed
    dates = pd.read_sql(
        "SELECT MAX(modification_date) AS last_mod, "
        "MAX(creation_date) AS last_new "
        "FROM source_data;",
        con=engine
    )

    last_mod = dates["last_mod"].iloc[0]
    last_new = dates["last_new"].iloc[0]

    service = pyvo.dal.TAPService("http://voparis-tap-planeto.obspm.fr/tap") 

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

    updates_df.to_sql(
    "source_data",
    con=engine,
    if_exists="append",
    index=False
    )

    with engine.begin() as conn:
        conn.exec_driver_sql("""
            DELETE FROM source_data
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM source_data
                GROUP BY target_name
            );
        """)

def fill_esi(engine: Engine):
    df = pd.read_sql(
    "SELECT * FROM source_data",
    con=engine
    )

    def calculate_esi(row):
        star_radius = row['star_radius']            # in solar radii
        star_teff = row['star_teff']                # in Kelvin
        semi_major_axis = row['semi_major_axis']    # in AU
        planetary_radius = row['radius']  # in Earth radii
        planetary_mass = row['mass'] # in earth mass

        if pd.isna(planetary_radius):
            planetary_radius = planetary_mass ** (1/3)

        luminosity = (star_radius ** 2) * ((star_teff / sun_teff) **4 )
        stellar_flux = (luminosity / (semi_major_axis) ** 2)
        flux_diff = ((stellar_flux - 1) / (stellar_flux + 1)) ** 2
        radius_diff = ((planetary_radius - 1) / (planetary_radius + 1)) ** 2
        esi = 1 - numpy.sqrt((flux_diff + radius_diff) / 2)
        return esi

    df["esi"] = df.apply(calculate_esi, axis=1)

    df["calculated_on"] = datetime.now()

    engine = create_engine("sqlite:///exoplanet_catalogue.db")

    df[["target_name", "esi", "creation_date", "calculated_on"]].to_sql("exoplanet_esis", index=False, con=engine, if_exists="replace", dtype={"planet_updated": Date})

def main():
    parser = argparse.ArgumentParser(description="Exoplanet catalogue utility")
    parser.add_argument("--db", type=str, default="exoplanet_catalogue.db", help="SQLite database filename")
    parser.add_argument("--retrieve", action="store_true", help="Retrieve full catalogue from TAP service")
    parser.add_argument("--update", action="store_true", help="Update catalogue with new/modified entries")
    parser.add_argument("--esi", action="store_true", help="Calculate ESI for all entries")
    
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