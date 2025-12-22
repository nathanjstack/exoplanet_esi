import pyvo
import pandas as pd

original_df = pd.read_csv("cleaned_data.csv")

# Update any exoplanets if new data is found
last_update = original_df["planet_updated"].max()
adjusted_date = f"{last_update}T00:00:00.000000"



service = pyvo.dal.TAPService("http://voparis-tap-planeto.obspm.fr/tap") 

query = f"""SELECT target_name, mass, radius, period, star_mass, star_radius, star_teff, semi_major_axis, modification_date, creation_date
FROM exoplanet.epn_core
WHERE modification_date > '{adjusted_date}'
    OR creation_date > '{adjusted_date}'
    AND mass IS NOT NULL
    AND period IS NOT NULL
    AND star_mass IS NOT NULL
    AND star_radius IS NOT NULL
    AND star_teff IS NOT NULL
    AND semi_major_axis IS NOT NULL
    AND discovered IS NOT NULL"""

results = service.search(query)
table = results.to_table()
df = table.to_pandas()

df.to_csv("test.csv", index=False)
