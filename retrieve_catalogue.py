import pyvo
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy import Engine
from sqlalchemy import text
from sqlalchemy.types import Date
import numpy
from datetime import datetime
import argparse

service = pyvo.dal.TAPService("https://exoplanetarchive.ipac.caltech.edu/TAP") 
sun_teff = 5778

def create_schema(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS source_data (
                pl_name TEXT,
                pl_bmasse REAL,
                pl_rade REAL,
                pl_orbper REAL,
                st_mass REAL,
                st_rad REAL,
                st_teff REAL,
                pl_orbsmax REAL,
                rowupdate DATE,
                releasedate DATE
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS exoplanet_esis (
                pl_name TEXT,
                esi REAL,
                releasedate DATE,
                calculated_on DATE,
                radius_estimated INTEGER
            );
        """))


def retrieve_catalogue(engine: Engine):
    '''
    Retrieve the current catalogue using the NASA Exoplanet Archive
    that have the values required to calculate ESI, exporting it to an SQLite database.

    Args:
        engine (Engine): an SQLalchemy engine connected to the target SQLite database

    Returns:
        None
    '''

    # Find exoplanets where relevant fields are not null and either mass or radius is not null

    print("Retrieving or updating completely new database...")

    query = f"""SELECT pl_name, pl_bmasse, pl_rade, pl_orbper, st_mass, st_rad, st_teff, pl_orbsmax, rowupdate, releasedate
    FROM ps
    WHERE pl_name IS NOT NULL
        AND (pl_bmasse IS NOT NULL
        OR pl_rade IS NOT NULL)

        AND pl_orbper IS NOT NULL
        AND st_mass IS NOT NULL
        AND st_rad IS NOT NULL
        AND st_teff IS NOT NULL
        AND pl_orbsmax IS NOT NULL
        AND rowupdate IS NOT NULL
        AND releasedate IS NOT NULL
        """

    results = service.search(query)
    table = results.to_table()
    df = table.to_pandas()
    
    first_planet = df.iloc[0]["pl_name"]
    print(f"Successfully retrieved database with {first_planet} and {len(df)-1} other exoplanets.")

    df["rowupdate"] = pd.to_datetime(df["rowupdate"])
    df["releasedate"] = pd.to_datetime(df["rowupdate"])

    df.to_sql("source_data", 
            index=False, 
            con=engine, 
            if_exists="replace",
            dtype={
                "rowupdate": Date,
                "releasedate": Date
            }
    )
    
    print(f"Database stored in {engine.url}")

def update_catalogue(engine: Engine):
    '''
    Update the current catalogue by calling the NASA Exoplanet TAP to 
    check if the modification date of exoplanets are more recent than what is in
    the local database, or if there have been any new exoplanets added.

    Args:
        engine (Engine): an SQLalchemy engine connected to the target SQLite database

    Returns:
        None
    '''
    dates = pd.read_sql(
        "SELECT MAX(rowupdate) AS last_update, "
        "MAX(releasedate) AS last_new "
        "FROM source_data;",
        con=engine
    )

    last_update = dates["last_update"].iloc[0]
    last_new = dates["last_new"].iloc[0]

    print("Checking for any updates or new entries...")

    # equality check on dates neccesary as date does not use timestamps, so planets
    # could be missed if updated halfway through the day otherwise
    query = f"""SELECT pl_name, pl_bmasse, pl_rade, pl_orbper, st_mass, st_rad, st_teff, pl_orbsmax, rowupdate, releasedate
    FROM ps
    WHERE (rowupdate >= '{last_update}'
        OR releasedate >= '{last_new}')

        AND pl_name IS NOT NULL
        AND pl_orbper IS NOT NULL
        AND st_mass IS NOT NULL
        AND st_rad IS NOT NULL
        AND st_teff IS NOT NULL
        AND pl_orbsmax IS NOT NULL
        AND rowupdate IS NOT NULL
        AND releasedate IS NOT NULL
        """

    results = service.search(query)
    table = results.to_table()
    updates_df = table.to_pandas()

    if len(updates_df) > 0:        
        print(f"Added or updated {len(updates_df)} exoplanet entries.")
        # create a temporary 'staging' table to store updated entries
        temp_table_name = "temp_updates"
        updates_df.to_sql(temp_table_name, engine, if_exists='replace', index=False)

        # delete entries that are in both source data and the staging table
        with engine.begin() as conn:
            delete_query = text(f"""
            DELETE FROM source_data
            WHERE pl_name IN (SELECT pl_name FROM {temp_table_name})
            """)

            # re-insert entries to source data
            conn.execute(delete_query)
            insert_query = text(f"""
            INSERT INTO source_data
            SELECT * FROM {temp_table_name}
            """)

            conn.execute(insert_query)

            conn.execute(text(f"DROP TABLE {temp_table_name}"))
    else:
        print("No updates found.")

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
    df["radius_estimated"] = df["pl_rade"].isna()

    def calculate_esi(row):
        star_radius = row['st_rad']            # in solar radii
        star_teff = row['st_teff']             # in Kelvin
        semi_major_axis = row['pl_orbsmax']    # in AU
        planetary_radius = row['pl_rade']      # in Earth Rad
        planetary_mass = row['pl_bmasse']     # Earth Mass

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
    df[["pl_name", "esi", "releasedate", "calculated_on", "radius_estimated"]].to_sql("exoplanet_esis", index=False, con=engine, if_exists="replace", dtype={"calculated_on": Date})
    print(f"ESIs successfully calculated and outputted in the 'exoplanet_esis' table of {engine.url}")

def main():
    parser = argparse.ArgumentParser(description="Exoplanet catalogue utility")
    parser.add_argument("-d", "--db", type=str, default="exoplanet_catalogue.db", help="SQLite database filename")
    parser.add_argument("-r", "--retrieve", action="store_true", help="Retrieve full catalogue from NASA Exoplanet Archive")
    parser.add_argument("-u", "--update", action="store_true", help="Update catalogue with new or modified exoplanet entries")
    parser.add_argument("-e", "--esi", action="store_true", help="Calculate ESI for all entries and create new table")
    parser.add_argument("-t", "--table", default="exoplanet_catalogue.db", action="store_true", help="Specify table name for ESI calculations")
    
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