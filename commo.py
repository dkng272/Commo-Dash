#%%
import pyodbc
import pandas as pd
import re
from pathlib import Path
import platform
from typing import Optional, Sequence
from anhem_db import DB_AILAB_STR, top_rows_dataframe

# Table Schema
# Ticker_Reference: Ticker, Name, Sector, Data_Source, Active
# Data Table: Ticker, Date, Price

#%% 
ticker_ref = top_rows_dataframe('Ticker_Reference','dbo',limit = None)
ticker_ref['Name'] = ticker_ref['Name'].str.strip() # remove blank spaces in the names
ticker_ref['Ticker'] = ticker_ref['Ticker'].str.strip() # remove blank spaces in the names
ticker_name_dict = dict(zip(ticker_ref['Ticker'],ticker_ref['Name']))

# Load all commodity data
full_data = []
for table_name in ticker_ref.Sector.unique():
    if table_name != 'Textile':
        df = top_rows_dataframe(table_name,'dbo',limit = None)
        full_data.append(df)

full_data = pd.concat(full_data,ignore_index=True)
full_data['Name'] = full_data['Ticker'].map(ticker_name_dict)

