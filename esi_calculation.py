import math
import pandas as pd

sun_teff = 5778

df = pd.read_csv("cleaned_data.csv")


def calculate_esi(row):
    star_radius = row['star_radius']            # in solar radii
    star_teff = row['star_teff']                # in Kelvin
    semi_major_axis = row['semi_major_axis']    # in AU
    planetary_radius = row['planetary_radius']  # in Earth radii

    luminosity = (star_radius ** 2) * ((star_teff / sun_teff) **4 )
    stellar_flux = (luminosity / (semi_major_axis) ** 2)
    flux_diff = ((stellar_flux - 1) / (stellar_flux + 1)) ** 2
    radius_diff = ((planetary_radius - 1) / (planetary_radius + 1)) ** 2
    esi = 1 - math.sqrt((flux_diff + radius_diff) / 2)
    return esi

df['esi'] = df.apply(calculate_esi, axis=1)

df.to_csv("esis.csv", index=False)