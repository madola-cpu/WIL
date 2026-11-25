# wages.csv

The columns are `soc_code,title,mean_hourly_wage,source`.

## How to fill it

Build the file by hand from the BLS Occupational Employment and Wage Statistics (OEWS) **May 2025 national estimates**. Get them from the "National" XLSX at bls.gov/oes.

- Add one row per SOC code that appears in `people.csv`.
- Set `source` to `BLS OEWS May 2025 national`.

bls.gov refuses automated downloads, so this file ships with the header only. Never type wages from memory.

## What happens while a code is missing

While a SOC code has no row here, the engine reports dollars as "not computed" and names the missing code.

A client can supply its own rates instead. Put `client_rates.csv` (`role,loaded_rate`) in the data folder, and the engine labels those dollars "client rate".
