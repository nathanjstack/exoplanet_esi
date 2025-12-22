import pandas as pd
import numpy as np

df = pd.read_csv("exoplanet.eu_catalog_19-12-25_06_56_25.csv")

cleaned_df = df[["name", "mass", "radius", "orbital_period", "star_mass", "star_radius", "star_teff", "semi_major_axis", "updated", "discovered"]].rename(columns = {
    "name": "planet_name",
    "mass": "planetary_mass",
    "radius": "planetary_radius",
    "updated": "planet_updated",
    "discovered": "planet_discovered"
})

# remove any rows that have neither mass or radius (not enough information to calculate ESI)
cleaned_df = cleaned_df.dropna(subset=["planetary_mass", "planetary_radius"])

# converting from jupiter to earth mass (refactor this code make these constants)
cleaned_df["planetary_mass"] = cleaned_df["planetary_mass"].apply(lambda x: x * 317.93842034806)
# converting from jupiter to earth radius
cleaned_df["planetary_radius"] = cleaned_df["planetary_radius"].apply(lambda x: x * 11.209)

# mass radius estimations
cleaned_df["planetary_mass"] = cleaned_df["planetary_mass"].fillna(cleaned_df["planetary_radius"] ** 3)
cleaned_df["planetary_mass"] = cleaned_df["planetary_mass"].fillna(cleaned_df["planetary_radius"] ** 1/3)

# remove any remaining rows with empty values
cleaned_df = cleaned_df.dropna()

cleaned_df.to_csv("cleaned_data.csv", index=False)